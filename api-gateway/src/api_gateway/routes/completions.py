import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import datetime
import litellm
import json
import httpx

from shared.database import get_db_session, async_session_maker
from shared.models import GatewayKey, RequestLog
from shared.schemas import ChatCompletionRequest, CompletionRequest
from router.core import select_model, get_ranked_candidates
from router.adapters import get_adapter
from router.quota import mark_provider_failed, record_success
from selfheal.incident_tracker import record_incident
from selfheal.adaptive_cooldown import record_failure as adaptive_record_failure, reset_failure_count

from api_gateway.auth import get_current_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Completions"])

async def log_request_bg_task(bg_data: dict):
    try:
        import uuid
        
        cred_id = bg_data.get("credential_id")
        if cred_id and isinstance(cred_id, str):
            try:
                cred_id = uuid.UUID(cred_id)
            except ValueError:
                cred_id = None
                
        client_key_id = bg_data.get("client_key_id")
        if client_key_id and isinstance(client_key_id, str):
            try:
                client_key_id = uuid.UUID(client_key_id)
            except ValueError:
                client_key_id = None

        async with async_session_maker() as session:
            log_entry = RequestLog(
                client_key_id=client_key_id,
                credential_id=cred_id,
                model_alias=bg_data.get("model_alias"),
                actual_model=bg_data.get("actual_model"),
                provider=bg_data.get("provider"),
                prompt_tokens=bg_data.get("prompt_tokens", 0),
                completion_tokens=bg_data.get("completion_tokens", 0),
                cost_usd=bg_data.get("cost_usd", 0.0),
                latency_ms=bg_data.get("latency_ms", 0),
                status=bg_data.get("status", "unknown"),
                prompt_json=bg_data.get("prompt_json"),
                response_text=bg_data.get("response_text")
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        logger.error("Failed to persist request log: %s", e)

async def _stream_generator(response, start_time: float, bg_data: dict, is_text_completion: bool = False):
    """
    Generator that yields SSE chunks and logs the completed stream data.
    """
    completion_text = ""
    prompt_tokens = bg_data.get("prompt_tokens", 0)
    completion_tokens = 0
    cost_usd = 0.0

    try:
        async for chunk in response:
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                if is_text_completion:
                    content = chunk.choices[0].text or ""
                else:
                    content = chunk.choices[0].delta.content or ""
                    
                completion_text += content
                completion_tokens += 1
            
            # For litellm streams, we must yield the model-dumped JSON
            if hasattr(chunk, 'model_dump_json'):
                data = chunk.model_dump_json()
            else:
                data = json.dumps(chunk)
                
            yield f"data: {data}\n\n"
            
        yield "data: [DONE]\n\n"
        
        # Estimate cost: cost_in / cost_out are already per-1k-tokens,
        # so divide token count by 1000 to get the USD amount.
        cost_usd = (
            prompt_tokens * bg_data.get("cost_in", 0.0)
            + completion_tokens * bg_data.get("cost_out", 0.0)
        ) / 1000.0
        bg_data["status"] = "success_stream"

    except Exception as e:
        logger.error("Stream error for %s/%s: %s", bg_data.get('provider'), bg_data.get('actual_model'), e, exc_info=True)
        
        # litellm exceptions can sometimes contain raw bytes `b"{...}"` in their string representation
        # which looks ugly or fails to parse nicely on the frontend.
        err_msg = str(e)
        if hasattr(e, "message"):
            err_msg = str(e.message)
            
        if err_msg.startswith("b'") or err_msg.startswith('b"'):
            try:
                # Strip b'' and decode unicode escapes
                raw = eval(err_msg).decode('utf-8')
                parsed = json.loads(raw)
                if "error" in parsed and "message" in parsed["error"]:
                    err_msg = parsed["error"]["message"]
            except:
                pass

        bg_data["status"] = f"error_stream: {err_msg}"
        yield f"data: {json.dumps({'error': err_msg})}\n\n"

    finally:
        latency_ms = int((datetime.datetime.now().timestamp() - start_time) * 1000)
        
        bg_data["completion_tokens"] = completion_tokens
        bg_data["cost_usd"] = cost_usd
        bg_data["latency_ms"] = latency_ms
        bg_data["response_text"] = completion_text
        if "status" not in bg_data:
            bg_data["status"] = "cancelled"

        # Persist the log directly here instead of via BackgroundTask
        # to guarantee logging happens after stream data is fully accumulated.
        await log_request_bg_task(bg_data)

@router.post("/chat/completions")
async def create_chat_completion(
    request: Request,
    body: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    key: GatewayKey = Depends(get_current_key),
    session: AsyncSession = Depends(get_db_session)
):
    start_time = datetime.datetime.now().timestamp()
    logger.info("Chat completion request: model=%s stream=%s key=%s", body.model, body.stream, key.label)
    
    try:
        candidates = await get_ranked_candidates(session, body.model, body)
        last_error = "No candidates found" if not candidates else None
        logger.info("Routing resolved %d candidate(s) for alias '%s'", len(candidates), body.model)
    except RuntimeError as e:
        candidates = []
        last_error = str(e)
        logger.warning("No routing candidates for '%s': %s", body.model, last_error)
        
    prompt_json = json.dumps([m.model_dump() for m in body.messages])
    
    for candidate in candidates:
        provider_name = candidate.provider
        actual_model = candidate.model_id
        
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from shared.models import Credential
        res = await session.execute(
            select(Credential)
            .options(selectinload(Credential.provider))
            .where(Credential.id == candidate.credential_id)
        )
        credential = res.scalar_one()
        
        # cost_in / cost_out: price per 1k tokens (used later as: tokens * rate / 1000)
        cost_in = candidate.input_cost_per_1k
        cost_out = candidate.output_cost_per_1k

        adapter = get_adapter(provider_name)
        
        try:
            kwargs = body.model_dump(exclude={"model", "messages", "stream"})
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            
            # Format prompt string correctly if using text completion vs chat completion
            # litellm proxying usually handles this transparently
            
            logger.info("Trying provider=%s model=%s (cred=%s)", provider_name, actual_model, credential.label)
            response = await adapter.chat(
                credential=credential,
                messages=body.model_dump()["messages"],
                model=actual_model,
                stream=body.stream,
                **kwargs
            )
            
            try:
                import litellm
                prompt_tokens = litellm.token_counter(model=actual_model, messages=body.model_dump()["messages"])
            except Exception:
                prompt_tokens = 0

            bg_data = {
                "client_key_id": key.id,
                "model_alias": body.model,
                "actual_model": actual_model,
                "provider": provider_name,
                "prompt_tokens": prompt_tokens,
                "cost_in": cost_in,
                "cost_out": cost_out,
                "prompt_json": prompt_json,
                "credential_id": str(credential.id),
            }

            if body.stream:
                return StreamingResponse(
                    _stream_generator(response, start_time, bg_data, is_text_completion=False),
                    media_type="text/event-stream",
                )
            else:
                completion_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
                cost_usd = (prompt_tokens * cost_in + completion_tokens * cost_out) / 1000.0
                completion_text = response.choices[0].message.content if hasattr(response, 'choices') else ""
                
                latency_ms = int((datetime.datetime.now().timestamp() - start_time) * 1000)
                logger.info(
                    "Chat completion success: provider=%s model=%s tokens=%d/%d latency=%dms",
                    provider_name, actual_model, prompt_tokens, completion_tokens, latency_ms,
                )

                # Self-heal: reset adaptive cooldown on success
                await record_success(credential.id, actual_model)
                await reset_failure_count(credential.id, actual_model)
                
                bg_data.update({
                    "completion_tokens": completion_tokens,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "status": "success",
                    "response_text": completion_text
                })
                background_tasks.add_task(log_request_bg_task, bg_data)
                
                # Litellm response acts like a pydantic model in many cases
                if hasattr(response, 'model_dump'):
                    return response.model_dump()
                return response

        except httpx.ReadError as e:
            # Self-heal: record incident + adaptive cooldown
            ttl = await adaptive_record_failure(credential.id, actual_model)
            await mark_provider_failed(credential.id, actual_model, timeout_seconds=ttl)
            await record_incident(credential.id, actual_model, str(e), provider=provider_name)
            last_error = f"Connection error: {str(e)}"
            logger.warning("Connection error with %s/%s (cooldown %ds), failing over: %s", provider_name, actual_model, ttl, e)
            continue
        except Exception as e:
            # Self-heal: record incident + adaptive cooldown for all errors
            error_str = str(e).lower()
            ttl = await adaptive_record_failure(credential.id, actual_model)
            if "rate limit" in error_str or "429" in error_str or "unauthorized" in error_str or "timeout" in error_str or "connection" in error_str:
                await mark_provider_failed(credential.id, actual_model, timeout_seconds=ttl)
            await record_incident(credential.id, actual_model, str(e), provider=provider_name)
            last_error = str(e)
            logger.warning("Error with %s/%s (cooldown %ds), failing over: %s", provider_name, actual_model, ttl, last_error)
            continue
            
    # If we exhausted all candidates
    from router.config import get_routing_config
    
    latency_ms = int((datetime.datetime.now().timestamp() - start_time) * 1000)
    config = get_routing_config()
    exhaustion_msg = config.get("exhaustion_message", "We're sorry, no models or quota are available right now.")
    logger.warning("All candidates exhausted for '%s' (%dms): %s", body.model, latency_ms, last_error)

    bg_data_fail = {
        "client_key_id": key.id,
        "model_alias": body.model,
        "actual_model": "unknown",
        "provider": "exhausted",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "status": f"exhausted: {last_error}",
        "prompt_json": prompt_json,
        "response_text": exhaustion_msg,
        "credential_id": None
    }

    background_tasks.add_task(log_request_bg_task, bg_data_fail)
    raise HTTPException(status_code=503, detail=f"Model routing failed: {last_error}")


@router.post("/completions")
async def create_completion(
    request: Request,
    body: CompletionRequest,
    background_tasks: BackgroundTasks,
    key: GatewayKey = Depends(get_current_key),
    session: AsyncSession = Depends(get_db_session)
):
    start_time = datetime.datetime.now().timestamp()
    logger.info("Text completion request: model=%s stream=%s key=%s", body.model, body.stream, key.label)
    
    from shared.schemas import ChatRequest
    chat_req = ChatRequest(
        model=body.model,
        messages=[{"role": "user", "content": body.prompt}],
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        stream=body.stream,
    )
    try:
        candidates = await get_ranked_candidates(session, body.model, chat_req)
        last_error = "No candidates found" if not candidates else None
        logger.info("Routing resolved %d candidate(s) for text alias '%s'", len(candidates), body.model)
    except RuntimeError as e:
        candidates = []
        last_error = str(e)
        logger.warning("No routing candidates for text '%s': %s", body.model, last_error)
        
    prompt_json = json.dumps({"prompt": body.prompt})
    
    # Text Completion behaves almost identically to Chat Completion via litellm translation
    messages = [{"role": "user", "content": body.prompt}]
    
    for candidate in candidates:
        provider_name = candidate.provider
        actual_model = candidate.model_id
        
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from shared.models import Credential
        res = await session.execute(
            select(Credential)
            .options(selectinload(Credential.provider))
            .where(Credential.id == candidate.credential_id)
        )
        credential = res.scalar_one()
        
        # cost_in / cost_out: price per 1k tokens (used later as: tokens * rate / 1000)
        cost_in = candidate.input_cost_per_1k
        cost_out = candidate.output_cost_per_1k

        adapter = get_adapter(provider_name)
        
        try:
            kwargs = body.model_dump(exclude={"model", "prompt", "stream"})
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            
            response = await adapter.chat(
                credential=credential,
                messages=messages,
                model=actual_model,
                stream=body.stream,
                **kwargs
            )
            
            try:
                import litellm
                prompt_tokens = litellm.token_counter(model=actual_model, messages=messages)
            except Exception:
                prompt_tokens = 0

            bg_data = {
                "client_key_id": key.id,
                "model_alias": body.model,
                "actual_model": actual_model,
                "provider": provider_name,
                "prompt_tokens": prompt_tokens,
                "cost_in": cost_in,
                "cost_out": cost_out,
                "prompt_json": prompt_json,
                "credential_id": str(credential.id),
            }

            if body.stream:
                return StreamingResponse(
                    _stream_generator(response, start_time, bg_data, is_text_completion=True),
                    media_type="text/event-stream",
                )
            else:
                completion_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
                cost_usd = (prompt_tokens * cost_in + completion_tokens * cost_out) / 1000.0
                
                # Adapt chat response format to text completion format
                completion_text = response.choices[0].message.content if hasattr(response, 'choices') else ""
                
                latency_ms = int((datetime.datetime.now().timestamp() - start_time) * 1000)
                
                bg_data.update({
                    "completion_tokens": completion_tokens,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "status": "success",
                    "response_text": completion_text
                })
                background_tasks.add_task(log_request_bg_task, bg_data)
                
                res_dict = response.model_dump() if hasattr(response, 'model_dump') else dict(response)
                # Map message to text
                if "choices" in res_dict and len(res_dict["choices"]) > 0:
                    choice = res_dict["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        choice["text"] = choice["message"]["content"]
                        del choice["message"]
                
                return res_dict

        except httpx.ReadError as e:
            ttl = await adaptive_record_failure(credential.id, actual_model)
            await mark_provider_failed(credential.id, actual_model, timeout_seconds=ttl)
            await record_incident(credential.id, actual_model, str(e), provider=provider_name)
            last_error = f"Connection error: {str(e)}"
            logger.warning("Text completion connection error with %s/%s (cooldown %ds): %s", provider_name, actual_model, ttl, e)
            continue
        except Exception as e:
            error_str = str(e).lower()
            ttl = await adaptive_record_failure(credential.id, actual_model)
            if "rate limit" in error_str or "429" in error_str or "unauthorized" in error_str or "timeout" in error_str or "connection" in error_str:
                await mark_provider_failed(credential.id, actual_model, timeout_seconds=ttl)
            await record_incident(credential.id, actual_model, str(e), provider=provider_name)
            last_error = str(e)
            logger.warning("Text completion error with %s/%s (cooldown %ds): %s", provider_name, actual_model, ttl, last_error)
            continue
            
    # If we exhausted all candidates
    from router.config import get_routing_config
    
    latency_ms = int((datetime.datetime.now().timestamp() - start_time) * 1000)
    config = get_routing_config()
    exhaustion_msg = config.get("exhaustion_message", "We're sorry, no models or quota are available right now.")

    bg_data_fail = {
        "client_key_id": key.id,
        "model_alias": body.model,
        "actual_model": "unknown",
        "provider": "exhausted",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "status": f"exhausted: {last_error}",
        "prompt_json": prompt_json,
        "response_text": exhaustion_msg,
        "credential_id": None
    }

    background_tasks.add_task(log_request_bg_task, bg_data_fail)
    raise HTTPException(status_code=503, detail=f"Model routing failed: {last_error}")
