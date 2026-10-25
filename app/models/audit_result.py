from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

@dataclass
class AuditResult:
    total_active_mods: int = 0
    total_workshop_mods: int = 0
    total_depthmaps: int = 0
    total_depthmap_mb: float = 0.0
    est_native_vram_gb: float = 0.0
    total_fbx_animations: int = 0
    heavy_tiles: List[Tuple[str, str, int, float]] = field(default_factory=list)
    heavy_anim_mods: List[Tuple[str, str, int]] = field(default_factory=list)
    rejected_mod_ids: List[str] = field(default_factory=list)
    hardware_test_passed: bool = True
    required_memory_gb: float = 0.0
    available_commit_gb: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    log_verified: bool = False
    log_status: str = "Nenhum log verificado"
    log_diagnostic: str = ""
    log_detailed_diagnostics: List[str] = field(default_factory=list)
    mods_vfs_loaded: int = 0
    mods_lua_confirmed: int = 0
    mods_silent: int = 0
    mods_without_lua: List[str] = field(default_factory=list)
    sp_status: str = "PASS"
    mp_status: str = "FAIL"
    mp_issues: List[str] = field(default_factory=list)

    @property
    def is_green(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_green": self.is_green,
            "singleplayer_status": self.sp_status,
            "multiplayer_status": self.mp_status,
            "total_active_mods": self.total_active_mods,
            "total_workshop_mods": self.total_workshop_mods,
            "total_depthmaps": self.total_depthmaps,
            "total_fbx_animations": self.total_fbx_animations,
            "est_native_vram_gb": self.est_native_vram_gb,
            "mods_vfs_loaded": self.mods_vfs_loaded,
            "mods_lua_confirmed": self.mods_lua_confirmed,
            "mods_silent": self.mods_silent,
            "errors": self.errors,
            "warnings": self.warnings,
            "mp_issues": self.mp_issues
        }
