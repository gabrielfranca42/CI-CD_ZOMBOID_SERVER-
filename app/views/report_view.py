import json
import os
from app.models.audit_result import AuditResult
from app.models.system_specs import SystemSpecs

class ReportView:
    """Exports audit findings to Markdown or JSON files."""

    @staticmethod
    def export_markdown(specs: SystemSpecs, result: AuditResult, output_path: str):
        content = [
            "# Project Zomboid Mod CI/CD Quality Gate Report",
            "",
            f"- **Game Version:** {specs.game_version}",
            f"- **System RAM:** {specs.total_ram_gb} GB (Free: {specs.free_ram_gb} GB)",
            f"- **Active Mods:** {result.total_active_mods}",
            f"- **Installed Mods:** {result.total_workshop_mods}",
            f"- **DepthMaps:** {result.total_depthmaps} ({result.total_depthmap_mb} MB) -> ~{result.est_native_vram_gb} GB VRAM",
            f"- **Runtime Log Evidence:** `{result.log_status}`",
            f"- **Mods VFS Loaded:** {result.mods_vfs_loaded}",
            f"- **Mods Lua Confirmed:** {result.mods_lua_confirmed}",
            f"- **Mods Silent (no Lua evidence):** {result.mods_silent}",
            "",
            "## Status Summary",
            f"- **Singleplayer:** `{result.sp_status}`",
            f"- **Multiplayer:** `{result.mp_status}`",
            f"- **Pipeline Decision:** `{'APPROVED' if result.is_green else 'REJECTED'}`",
            "",
        ]

        if result.errors:
            content.append("## Critical Failures")
            for err in result.errors:
                content.append(f"```\n{err}\n```")
            content.append("")

        if result.mp_issues:
            content.append("## Multiplayer Analysis")
            for issue in result.mp_issues:
                content.append(f"- {issue}")
            content.append("")

        if result.warnings:
            content.append("## Warnings")
            for warn in result.warnings[:15]:
                content.append(f"- {warn}")
            content.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    @staticmethod
    def export_json(result: AuditResult, output_path: str):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
