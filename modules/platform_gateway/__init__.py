"""Platform Gateway module for Web UI and SIEM integration."""
from modules.platform_gateway.service import PlatformGatewayService
from modules.platform_gateway.schemas import URLScanRequest, PlatformScanResponse

__all__ = ["PlatformGatewayService", "URLScanRequest", "PlatformScanResponse"]
