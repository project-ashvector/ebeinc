"""
ALLTHINGS140 Hub — Site Content & Media CMS Service
Manages zero-code-deploy content stores for Sponsors, Partners, Takeovers, Announcements, Roadmap, and Media Library.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import PROJECT_ROOT, get_config
from hub.util.atomic_io import atomic_write_json

SITE_CONTENT_PATH = PROJECT_ROOT / "radio" / "data" / "site-content.json"
SITE_ASSETS_DIR = PROJECT_ROOT / "radio" / "assets"


@dataclass
class SponsorItem:
    id: str
    name: str
    logoUrl: str
    websiteUrl: str
    description: str
    tier: str  # Headline, Stage, Underground, Community
    campaignStartDate: str = ""
    campaignEndDate: str = ""
    active: bool = True
    featured: bool = False
    ordering: int = 0


@dataclass
class PartnerItem:
    id: str
    name: str
    logoUrl: str
    websiteUrl: str
    description: str
    category: str  # Record Label, Festival, Sound System, Collective, Media
    active: bool = True
    ordering: int = 0


@dataclass
class TakeoverItem:
    id: str
    artist: str
    logoUrl: str
    date: str
    time: str
    status: str  # upcoming, live, completed, archive
    bio: str
    artistLinks: Dict[str, str] = field(default_factory=dict)  # soundcloud, instagram, spotify, etc.
    replayUrl: str = ""
    tracklist: List[str] = field(default_factory=list)
    featured: bool = False
    ordering: int = 0


@dataclass
class AnnouncementItem:
    id: str
    title: str
    content: str
    type: str  # info, event, urgent, broadcast
    date: str
    active: bool = True
    targetPlanes: List[str] = field(default_factory=lambda: ["web"])


@dataclass
class RoadmapItem:
    id: str
    title: str
    description: str
    quarter: str
    phase: str
    status: str  # completed, in-progress, planned
    ordering: int = 0


@dataclass
class MediaAsset:
    id: str
    filename: str
    relativePath: str
    absolutePath: str
    dimensions: str  # e.g. "1920x1080" or "512x512"
    sizeBytes: int
    sizeFormatted: str
    mimeType: str
    uploadDate: str
    usageCategory: str  # sponsor, partner, takeover, background, general
    usedIn: List[str] = field(default_factory=list)


class SiteContentService:
    """Manages site content records and media asset library."""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            try:
                project_root = Path(get_config().current_project_path).expanduser().resolve()
            except Exception:
                project_root = PROJECT_ROOT
        self.project_root = project_root
        self.load_error: str = ""
        self.content_file = self.project_root / "radio" / "data" / "site-content.json"
        self.assets_dir = self.project_root / "radio" / "assets"

        self.sponsors: List[SponsorItem] = []
        self.partners: List[PartnerItem] = []
        self.takeovers: List[TakeoverItem] = []
        self.announcements: List[AnnouncementItem] = []
        self.roadmap: List[RoadmapItem] = []
        self.media_assets: List[MediaAsset] = []

        self.reload()

    def reload(self) -> None:
        """Load real site content. Missing/corrupt data never creates fake records."""
        self.content_file.parent.mkdir(parents=True, exist_ok=True)
        self.sponsors = []
        self.partners = []
        self.takeovers = []
        self.announcements = []
        self.roadmap = []
        self.load_error = ""
        if self.content_file.exists():
            try:
                data = json.loads(self.content_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("site-content.json root must be an object")
                self.sponsors = [SponsorItem(**x) for x in data.get("sponsors", []) if isinstance(x, dict)]
                self.partners = [PartnerItem(**x) for x in data.get("partners", []) if isinstance(x, dict)]
                self.takeovers = [TakeoverItem(**x) for x in data.get("takeovers", []) if isinstance(x, dict)]
                self.announcements = [AnnouncementItem(**x) for x in data.get("announcements", []) if isinstance(x, dict)]
                self.roadmap = [RoadmapItem(**x) for x in data.get("roadmap", []) if isinstance(x, dict)]
            except Exception as exc:
                self.load_error = f"Could not load {self.content_file}: {exc}"
                # Preserve the damaged file for recovery. Never overwrite it with seeds.
                stamp = time.strftime("%Y%m%d-%H%M%S")
                corrupt_copy = self.content_file.with_suffix(self.content_file.suffix + f".corrupt-{stamp}")
                try:
                    shutil.copy2(self.content_file, corrupt_copy)
                except OSError:
                    pass
        self.scan_media_assets()

    def save(self) -> None:
        """Persist structured content atomically to avoid crash-truncated JSON."""
        data = {
            "version": "1.2.1",
            "lastUpdated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sponsors": [asdict(x) for x in self.sponsors],
            "partners": [asdict(x) for x in self.partners],
            "takeovers": [asdict(x) for x in self.takeovers],
            "announcements": [asdict(x) for x in self.announcements],
            "roadmap": [asdict(x) for x in self.roadmap],
        }
        atomic_write_json(self.content_file, data)
        self.load_error = ""

    def import_media(self, source_path: str | Path, category: str = "general") -> str:
        """Copy an operator-selected media file into the managed site assets tree.

        Returns a path relative to radio/, suitable for CMS logoUrl fields.
        """
        src = Path(source_path).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(src)
        allowed = {".png", ".webp", ".jpg", ".jpeg", ".svg", ".mp4"}
        if src.suffix.lower() not in allowed:
            raise ValueError(f"Unsupported media type: {src.suffix}")
        safe_category = "".join(c for c in category.lower() if c.isalnum() or c in ("-", "_")) or "general"
        dest_dir = self.assets_dir / "hub-managed" / safe_category
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in src.stem.lower()).strip("-") or "asset"
        dest = dest_dir / f"{stem}{src.suffix.lower()}"

        def same_file(a: Path, b: Path) -> bool:
            if not b.exists() or a.stat().st_size != b.stat().st_size:
                return False
            def digest(p: Path) -> str:
                h = hashlib.sha256()
                with p.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        h.update(chunk)
                return h.hexdigest()
            return digest(a) == digest(b)

        i = 2
        while dest.exists() and not same_file(src, dest):
            dest = dest_dir / f"{stem}-{i}{src.suffix.lower()}"
            i += 1
        if not dest.exists():
            shutil.copy2(src, dest)
        self.scan_media_assets()
        return str(dest.relative_to(self.project_root / "radio"))

    def scan_media_assets(self) -> List[MediaAsset]:
        """Scan radio/assets/ for images, videos, and icons with usage references."""
        assets = []
        if not self.assets_dir.exists():
            return assets

        # Build a conservative reference index across site source/data files.
        reference_texts: Dict[str, str] = {}
        radio_root = self.project_root / "radio"
        for pattern in ("**/*.html", "**/*.css", "**/*.js", "**/*.json", "**/*.mjs"):
            for src in radio_root.glob(pattern):
                if not src.is_file() or self.assets_dir in src.parents:
                    continue
                try:
                    if src.stat().st_size <= 2 * 1024 * 1024:
                        reference_texts[str(src.relative_to(self.project_root))] = src.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

        content_json_str = json.dumps([asdict(x) for x in self.sponsors + self.partners + self.takeovers])

        for item in sorted(self.assets_dir.glob("**/*")):
            if not item.is_file():
                continue
            if item.suffix.lower() not in (".webp", ".png", ".jpg", ".jpeg", ".svg", ".mp4", ".m3u8"):
                continue

            rel_path = str(item.relative_to(self.project_root / "radio"))
            stat = item.stat()
            size = stat.st_size
            mtime = stat.st_mtime
            upload_date = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            size_fmt = self._format_size(size)

            # Detect usage
            used_in = [name for name, text in reference_texts.items() if item.name in text or rel_path in text]
            if item.name in content_json_str or rel_path in content_json_str:
                used_in.append("Site Content CMS")

            # Determine category
            name_lower = item.name.lower()
            if "sponsor" in name_lower:
                category = "sponsor"
            elif "partner" in name_lower:
                category = "partner"
            elif "takeover" in name_lower:
                category = "takeover"
            elif "visual" in name_lower:
                category = "background"
            else:
                category = "general"

            mime = "image/" + item.suffix.lstrip(".").replace("jpg", "jpeg")
            if item.suffix.lower() == ".mp4":
                mime = "video/mp4"

            assets.append(MediaAsset(
                id=hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:16],
                filename=item.name,
                relativePath=rel_path,
                absolutePath=str(item),
                dimensions="Direct Asset",
                sizeBytes=size,
                sizeFormatted=size_fmt,
                mimeType=mime,
                uploadDate=upload_date,
                usageCategory=category,
                usedIn=used_in
            ))

        self.media_assets = assets
        return self.media_assets

    # Sponsors CRUD
    def add_sponsor(self, name: str, logo_url: str, website: str, description: str, tier: str = "Underground", active: bool = True, featured: bool = False) -> SponsorItem:
        sid = f"sponsor-{int(time.time())}-{name.lower().replace(' ', '-')[:16]}"
        item = SponsorItem(id=sid, name=name, logoUrl=logo_url, websiteUrl=website, description=description, tier=tier, active=active, featured=featured, ordering=len(self.sponsors))
        self.sponsors.append(item)
        self.save()
        return item

    def update_sponsor(self, sponsor_id: str, **kwargs) -> Optional[SponsorItem]:
        for s in self.sponsors:
            if s.id == sponsor_id:
                for k, v in kwargs.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
                self.save()
                return s
        return None

    def delete_sponsor(self, sponsor_id: str) -> bool:
        initial_len = len(self.sponsors)
        self.sponsors = [s for s in self.sponsors if s.id != sponsor_id]
        if len(self.sponsors) != initial_len:
            self.save()
            return True
        return False

    # Partners CRUD
    def add_partner(self, name: str, logo_url: str, website: str, description: str, category: str = "Record Label", active: bool = True) -> PartnerItem:
        pid = f"partner-{int(time.time())}-{name.lower().replace(' ', '-')[:16]}"
        item = PartnerItem(id=pid, name=name, logoUrl=logo_url, websiteUrl=website, description=description, category=category, active=active, ordering=len(self.partners))
        self.partners.append(item)
        self.save()
        return item

    def update_partner(self, partner_id: str, **kwargs) -> Optional[PartnerItem]:
        for p in self.partners:
            if p.id == partner_id:
                for k, v in kwargs.items():
                    if hasattr(p, k):
                        setattr(p, k, v)
                self.save()
                return p
        return None

    def delete_partner(self, partner_id: str) -> bool:
        initial_len = len(self.partners)
        self.partners = [p for p in self.partners if p.id != partner_id]
        if len(self.partners) != initial_len:
            self.save()
            return True
        return False

    # Takeovers CRUD
    def add_takeover(self, artist: str, logo_url: str, date: str, time_str: str, status: str, bio: str, links: Optional[Dict[str, str]] = None, replay_url: str = "", tracklist: Optional[List[str]] = None, featured: bool = False) -> TakeoverItem:
        tid = f"takeover-{int(time.time())}-{artist.lower().replace(' ', '-')[:16]}"
        item = TakeoverItem(id=tid, artist=artist, logoUrl=logo_url, date=date, time=time_str, status=status, bio=bio, artistLinks=links or {}, replayUrl=replay_url, tracklist=tracklist or [], featured=featured, ordering=len(self.takeovers))
        self.takeovers.insert(0, item)
        self.save()
        return item

    def update_takeover(self, takeover_id: str, **kwargs) -> Optional[TakeoverItem]:
        for t in self.takeovers:
            if t.id == takeover_id:
                for k, v in kwargs.items():
                    if hasattr(t, k):
                        setattr(t, k, v)
                self.save()
                return t
        return None

    def delete_takeover(self, takeover_id: str) -> bool:
        initial_len = len(self.takeovers)
        self.takeovers = [t for t in self.takeovers if t.id != takeover_id]
        if len(self.takeovers) != initial_len:
            self.save()
            return True
        return False

    # Announcements CRUD
    def add_announcement(self, title: str, content: str, ann_type: str = "info", active: bool = True, target_planes: Optional[List[str]] = None) -> AnnouncementItem:
        aid = f"ann-{int(time.time())}"
        date_str = time.strftime("%Y-%m-%d")
        item = AnnouncementItem(id=aid, title=title, content=content, type=ann_type, date=date_str, active=active, targetPlanes=target_planes or ["web"])
        self.announcements.insert(0, item)
        self.save()
        return item

    def delete_announcement(self, ann_id: str) -> bool:
        self.announcements = [a for a in self.announcements if a.id != ann_id]
        self.save()
        return True

    # Roadmap CRUD
    def add_roadmap_item(self, title: str, description: str, quarter: str, phase: str, status: str = "in-progress") -> RoadmapItem:
        rid = f"road-{int(time.time())}"
        item = RoadmapItem(id=rid, title=title, description=description, quarter=quarter, phase=phase, status=status, ordering=len(self.roadmap))
        self.roadmap.append(item)
        self.save()
        return item

    def update_roadmap_item(self, road_id: str, **kwargs) -> Optional[RoadmapItem]:
        for r in self.roadmap:
            if r.id == road_id:
                for k, v in kwargs.items():
                    if hasattr(r, k):
                        setattr(r, k, v)
                self.save()
                return r
        return None

    def _seed_initial_content(self) -> None:
        """Deprecated: v1.2.1 never fabricates sponsors, partners, takeovers, or activity."""
        self.sponsors = []
        self.partners = []
        self.takeovers = []
        self.announcements = []
        self.roadmap = []

    def quarantine_media(self, asset_path: str | Path) -> Path:
        """Move a media asset out of the live assets tree into a reversible quarantine."""
        src = Path(asset_path).expanduser().resolve()
        assets_root = self.assets_dir.resolve()
        if not src.is_file() or assets_root not in src.parents:
            raise ValueError("Only files inside the managed radio/assets directory can be quarantined")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        qdir = self.project_root / "backups" / "site-media-quarantine" / stamp
        qdir.mkdir(parents=True, exist_ok=True)
        dest = qdir / src.name
        i = 2
        while dest.exists():
            dest = qdir / f"{src.stem}-{i}{src.suffix}"
            i += 1
        shutil.move(str(src), str(dest))
        self.scan_media_assets()
        return dest

    def _format_size(self, b: int) -> str:
        if b < 1024:
            return f"{b} B"
        elif b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        else:
            return f"{b / (1024 * 1024):.1f} MB"
