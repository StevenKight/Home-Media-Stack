"""
media.py

Routes for searching, adding, and removing media (TV series via Sonarr,
movies via Radarr) through the unified MediaClient.

Endpoints:
    GET  /media/search              - Search Sonarr + Radarr for a title
    GET  /media/library             - List everything currently in both libraries
    GET  /media/library/{type}/{id} - Get the details (incl. download status) of a single library item
    POST /media/add                 - Add a search result to the correct library and start downloading it
    POST /media/remove              - Remove a library item from its backend

Security:
    All endpoints require a valid JWT bearer token.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.models import User
from app.routes.auth import get_current_user
from app.schemas.media import (
    AddMediaRequest,
    DownloadStatusResponse,
    MediaResultResponse,
    MediaSearchResultResponse,
    RemoveMediaRequest,
)
from app.services.media import MediaClient, MediaError, MediaResult, MediaType
from app.services.radarr import RadarrError
from app.services.sonarr import SonarrError

router = APIRouter(prefix="/media", tags=["media"])

BackendErrors = (MediaError, SonarrError, RadarrError)


def get_media_client() -> MediaClient:
    return MediaClient()


def _to_media_result_response(item: MediaResult) -> MediaResultResponse:
    download_status = (
        DownloadStatusResponse(
            status=item.download_status.status,
            tracked_download_state=item.download_status.tracked_download_state,
            tracked_download_status=item.download_status.tracked_download_status,
            title=item.download_status.title,
            size=item.download_status.size,
            size_remaining=item.download_status.size_remaining,
            time_remaining=item.download_status.time_remaining,
            estimated_completion=item.download_status.estimated_completion,
            protocol=item.download_status.protocol,
            download_client=item.download_status.download_client,
            indexer=item.download_status.indexer,
            error_message=item.download_status.error_message,
        )
        if item.download_status
        else None
    )
    return MediaResultResponse(
        media_type=item.media_type,
        id=item.id,
        title=item.title,
        monitored=item.monitored,
        external_id=item.external_id,
        year=item.year,
        overview=item.overview,
        poster_url=item.poster_url,
        fanart_url=item.fanart_url,
        genres=item.genres,
        runtime=item.runtime,
        rating=item.rating,
        network=item.network,
        studio=item.studio,
        download_status=download_status,
    )


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

    return [_to_media_result_response(i) for i in items]


@router.get("/library/{media_type}/{id}", response_model=MediaResultResponse)
def get_library_item(
    media_type: MediaType,
    id: int,
    current_user: User = Depends(get_current_user),
    client: MediaClient = Depends(get_media_client),
):
    """
    Return the details of a single library item, including its current
    download status if Sonarr/Radarr has it queued or downloading.

    Args:
        media_type: Whether `id` refers to a series (Sonarr) or movie (Radarr).
        id: The Sonarr or Radarr internal id, as returned by /media/library.

    Raises:
        HTTPException: 502 if Sonarr/Radarr can't be reached or the item doesn't exist.
    """
    try:
        item = client.get_item(media_type, id)
    except BackendErrors as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return _to_media_result_response(item)


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

    return _to_media_result_response(added)


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
