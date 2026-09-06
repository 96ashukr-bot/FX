import hmac

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ExecutionNode


class ExecutionNodePrincipal:
    is_authenticated = True

    def __init__(self, node):
        self.node = node


class ExecutionNodeAuthentication(BaseAuthentication):
    keyword = "Node"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith(f"{self.keyword} "):
            return None
        raw = header[len(self.keyword) + 1:].strip()
        prefix = raw[:12]
        candidates = ExecutionNode.objects.select_related("tenant", "account").filter(
            credential_prefix=prefix,
            is_active=True,
            tenant__is_active=True,
            account__is_enabled=True,
        )
        supplied_hash = ExecutionNode.hash_credential(raw)
        node = next((item for item in candidates if hmac.compare_digest(item.credential_hash, supplied_hash)), None)
        if not node:
            raise AuthenticationFailed("Invalid execution-node credential")
        request.execution_node = node
        request.tenant = node.tenant
        return ExecutionNodePrincipal(node), node
