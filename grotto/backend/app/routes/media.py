"""
media.py

Routes for searching, adding, and removing media (TV series via Sonarr,
movies via Radarr) through the unified MediaClient.

Endpoints:
    GET  /media/search   - Search Sonarr + Radarr for a title
    GET  /media/library  - List everything currently in both libraries
    POST /media/add      - Add a search result to the correct library and start downloading it
    POST /media/remove   - Remove a library item from its backend

Security:
    All endpoints require a valid JWT bearer token.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.models import User
from app.routes.auth import get_current_user
from app.schemas.media import (
    AddMediaRequest,
    MediaResultResponse,
    MediaSearchResultResponse,
    RemoveMediaRequest,
)
from app.services.media import MediaClient, MediaError
from app.services.radarr import RadarrError
from app.services.sonarr import SonarrError

router = APIRouter(prefix="/media", tags=["media"])

BackendErrors = (MediaError, SonarrError, RadarrError)


def get_media_client() -> MediaClient:
    return MediaClient()


@router.get("/search", response_model=list[MediaSearchResultResponse])
def search_media(
    term: str,
    current_user: User = Depends(get_current_user),
    client: MediaClient = Depends(get_media_client),
):
    """
    Search Sonarr and Radarr for a title.

    Args:
        term: Title (or partial title) to search for.

    Returns:
        Combined TV and movie matches.

    Raises:
        HTTPException: 502 if Sonarr/Radarr can't be reached.
    """
    try:
        results = client.search(term)
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return [
        MediaSearchResultResponse(
            media_type=r.media_type,
            title=r.title,
            year=r.year,
            overview=r.overview,
            already_in_library=r.already_in_library,
            external_id=r.external_id,
            poster_url=r.poster_url,
            fanart_url=r.fanart_url,
            genres=r.genres,
            runtime=r.runtime,
            rating=r.rating,
            network=r.network,
            studio=r.studio,
        )
        for r in results
    ]


@router.get("/library", response_model=list[MediaResultResponse])
def list_library(
    current_user: User = Depends(get_current_user),
    client: MediaClient = Depends(get_media_client),
):
    """
    Return everything currently in the Sonarr and Radarr libraries.

    Raises:
        HTTPException: 502 if Sonarr/Radarr can't be reached.
    """
    try:
        items = client.get_library()
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return [
        MediaResultResponse(
            media_type=i.media_type,
            id=i.id,
            title=i.title,
            monitored=i.monitored,
            external_id=i.external_id,
            year=i.year,
            overview=i.overview,
            poster_url=i.poster_url,
            fanart_url=i.fanart_url,
            genres=i.genres,
            runtime=i.runtime,
            rating=i.rating,
            network=i.network,
            studio=i.studio,
        )
        for i in items
    ]


@router.post("/add", response_model=MediaResultResponse)
def add_media(
    request: AddMediaRequest,
    current_user: User = Depends(get_current_user),
    client: MediaClient = Depends(get_media_client),
):
    """
    Add a previously-searched title to the correct library and start
    downloading it.

    Search results aren't cached server-side, so this re-runs the search
    for `term` to locate the exact match by `media_type`/`external_id`
    before adding it.

    Raises:
        HTTPException: 404 if the match can no longer be found, 502 if the
            backend rejects the add request.
    """
    try:
        matches = [
            r
            for r in client.search(request.term)
            if r.media_type == request.media_type and r.external_id == request.external_id
        ]
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match found for term='{request.term}' external_id={request.external_id}",
        )

    try:
        added = client.add(
            matches[0],
            quality_profile_id=request.quality_profile_id,
            root_folder_path=request.root_folder_path,
            monitored=request.monitored,
            search_now=request.search_now,
        )
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return MediaResultResponse(
        media_type=added.media_type,
        id=added.id,
        title=added.title,
        monitored=added.monitored,
        external_id=added.external_id,
        year=added.year,
        overview=added.overview,
        poster_url=added.poster_url,
        fanart_url=added.fanart_url,
        genres=added.genres,
        runtime=added.runtime,
        rating=added.rating,
        network=added.network,
        studio=added.studio,
    )


@router.post("/remove")
def remove_media(
    request: RemoveMediaRequest,
    current_user: User = Depends(get_current_user),
    client: MediaClient = Depends(get_media_client),
):
    """
    Remove a library item from whichever backend it belongs to.

    Raises:
        HTTPException: 404 if no matching library item is found, 502 if the
            backend rejects the remove request.
    """
    try:
        matches = [
            i for i in client.get_library() if i.media_type == request.media_type and i.id == request.id
        ]
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {request.media_type.value} with id {request.id} found in the library",
        )

    try:
        client.remove(
            matches[0],
            delete_files=request.delete_files,
            add_exclusion=request.add_exclusion,
        )
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return {"message": f"Removed '{matches[0].title}' from the library"}
