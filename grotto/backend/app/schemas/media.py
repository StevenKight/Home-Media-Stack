"""
media.py

Pydantic models for the media search/add/remove API.

Wraps the MediaType enum and result shapes from app.services.media for use
as FastAPI request/response models.
"""

from pydantic import BaseModel

from app.services.media import MediaType


class MediaSearchResultResponse(BaseModel):
    media_type: MediaType
    title: str
    year: int | None
    overview: str | None
    already_in_library: bool
    external_id: int
    poster_url: str | None
    fanart_url: str | None
    genres: list[str]
    runtime: int | None
    rating: float | None
    network: str | None
    studio: str | None


class MediaResultResponse(BaseModel):
    media_type: MediaType
    id: int
    title: str
    monitored: bool
    external_id: int
    year: int | None
    overview: str | None
    poster_url: str | None
    fanart_url: str | None
    genres: list[str]
    runtime: int | None
    rating: float | None
    network: str | None
    studio: str | None


class AddMediaRequest(BaseModel):
    media_type: MediaType
    term: str
    external_id: int
    quality_profile_id: int | None = None
    root_folder_path: str | None = None
    monitored: bool = True
    search_now: bool = True


class RemoveMediaRequest(BaseModel):
    media_type: MediaType
    id: int
    delete_files: bool = False
    add_exclusion: bool = False
