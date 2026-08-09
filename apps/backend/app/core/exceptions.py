from fastapi import HTTPException, status


class FlobriefError(Exception):
    def __init__(self, message: str, code: str = "internal_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(FlobriefError):
    def __init__(self, resource: str, resource_id: str | None = None) -> None:
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} '{resource_id}' not found"
        super().__init__(detail, "not_found")


class PermissionDeniedError(FlobriefError):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message, "permission_denied")


class ConflictError(FlobriefError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "conflict")


class ValidationError(FlobriefError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "validation_error")


class UnauthorizedError(FlobriefError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, "unauthorized")


def not_found(resource: str, resource_id: str | None = None) -> HTTPException:
    detail = f"{resource} not found"
    if resource_id:
        detail = f"{resource} '{resource_id}' not found"
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def permission_denied(message: str = "Permission denied") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
