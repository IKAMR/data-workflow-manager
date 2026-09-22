from .base import BaseExecutor
from noark5_workflow.core.events import WorkflowEvent
from noark5_workflow.core.identity import UserIdentity
from noark5_workflow.core.operation import BaseOperation
from noark5_workflow.core.raw_result_store import persist_operation_raw_result
from noark5_workflow.core.result import OperationResult
from noark5_workflow.logging_pipeline import event_dispatcher_for


class LocalExecutor(BaseExecutor):
    backend_id = "local"

    def execute(self, operation: BaseOperation, ctx) -> OperationResult:
        allowed, reason = operation.can_run(ctx)
        if not allowed:
            return OperationResult(False, reason or "Operasjonen kan ikke kjøres i denne konteksten.")

        result = operation.run(ctx)

        persist_operation_raw_result(operation, result, ctx)
        ctx.set_result(operation.definition.operation_id, result.data)

        identity = UserIdentity.from_mapping(
            ctx.settings.get("_current_user_identity")
            if isinstance(ctx.settings, dict)
            else None
        )
        run_id = str(
            ctx.metadata.get("run_id", "")
            or ctx.settings.get("_current_run_id", "")
            or ""
        )
        event = WorkflowEvent.now(
            "operation.completed",
            run_id=run_id,
            job_id=str(ctx.metadata.get("job_id", "") or ""),
            success=bool(getattr(result, "ok", True)),
            message=str(getattr(result, "message", "") or ""),
            operation_id=str(getattr(operation.definition, "operation_id", "") or ""),
            operation_name=str(getattr(operation.definition, "name", "") or ""),
            user=identity,
            data={
                "warnings": list(getattr(result, "warnings", []) or []),
                "result": getattr(result, "data", None),
            },
        )
        event_dispatcher_for(ctx).emit(
            event,
            operation=operation,
            result=result,
            ctx=ctx,
        )
        return result
