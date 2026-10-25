from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

@dataclass
class ServerAuditResult:
    total_server_mods: int = 0
    total_workshop_items: int = 0
    missing_workshop_mappings: List[str] = field(default_factory=list)
    missing_map_mappings: List[str] = field(default_factory=list)
    host_memory_mb: int = 2048
    client_memory_gb: float = 4.0
    total_required_commit_gb: float = 0.0
    available_commit_gb: float = 0.0
    hardware_test_passed: bool = True
    build_failures: List[Tuple[str, str, List[str]]] = field(default_factory=list)  # (mod_id, mod_name, errors)

    # Core System Categories
    red_mods: List[Tuple[str, str, str]] = field(default_factory=list)     # (mod_id, mod_name, reason) - GRAVE / NÃO COMPILA / CRASH
    yellow_mods: List[Tuple[str, str, str]] = field(default_factory=list)  # (mod_id, mod_name, reason) - ALERTA / SUJEITO A ERRO
    green_mods: List[Tuple[str, str]] = field(default_factory=list)        # (mod_id, mod_name) - APROVADO

    # Legacy compatibility
    rejected_mod_ids: List[Tuple[str, str, str]] = field(default_factory=list)  # (mod_id, mod_name, reason)

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    server_status: str = "PASS"

    @property
    def is_green(self) -> bool:
        return len(self.red_mods) == 0 and len(self.errors) == 0 and self.hardware_test_passed

    @property
    def summary_counts(self) -> Dict[str, int]:
        return {
            "red": len(self.red_mods),
            "yellow": len(self.yellow_mods),
            "green": len(self.green_mods),
            "total": self.total_server_mods
        }
