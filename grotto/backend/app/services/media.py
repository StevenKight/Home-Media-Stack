"""
media.py

Unified client for searching, adding, and removing media across both Sonarr
(TV shows) and Radarr (movies). Wraps SonarrClient and RadarrClient so callers
don't need to know which backend a title belongs to - search() checks both,
add() routes to the right one, and remove() routes a library item back to
whichever system it came from.

Example:
    from app.services.media import MediaClient

    client = MediaClient()
    results = client.search("Alien")
    for item in results:
        print(item.media_type, item.title, item.year)

    added = client.add(results[0])
    client.remove(added, delete_files=True)

Run this file directly for an interactive search-and-download prompt:
    python -m app.services.media
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.services.radarr import MovieResult, MovieSearchResult, RadarrClient
from app.services.sonarr import SeriesResult, SeriesSearchResult, SonarrClient


class MediaType(str, Enum):
    SERIES = "series"
    MOVIE = "movie"


class MediaError(Exception):
    """Raised when a media operation is invalid or its backend isn't configured."""


@dataclass
class MediaSearchResult:
    """A single search match from either Sonarr or Radarr."""

    media_type: MediaType
    title: str
    year: int | None
    overview: str | None
    already_in_library: bool
    external_id: int  # tvdbId for TV, tmdbId for movies
    poster_url: str | None
    fanart_url: str | None
    genres: list[str]
    runtime: int | None
    rating: float | None
    network: str | None  # set for series, None for movies
    studio: str | None  # set for movies, None for series
    source: SeriesSearchResult | MovieSearchResult


@dataclass
class MediaResult:
    """A media item that exists in either the Sonarr or Radarr library."""

    media_type: MediaType
    id: int
    title: str
    monitored: bool
    external_id: int  # tvdbId for TV, tmdbId for movies
    year: int | None
    overview: str | None
    poster_url: str | None
    fanart_url: str | None
    genres: list[str]
    runtime: int | None
    rating: float | None
    network: str | None  # set for series, None for movies
    studio: str | None  # set for movies, None for series
    source: SeriesResult | MovieResult


class MediaClient:
    """
    Combines SonarrClient and RadarrClient behind a single search/add/remove API.

    If either backend's API key isn't configured, that backend is simply
    skipped during search/library calls; trying to add/remove against an
    unconfigured backend raises MediaError.
    """

    def __init__(
        self,
        sonarr: SonarrClient | None = None,
        radarr: RadarrClient | None = None,
    ) -> None:
        self.sonarr = sonarr if sonarr is not None else self._try_init(SonarrClient)
        self.radarr = radarr if radarr is not None else self._try_init(RadarrClient)

    @staticmethod
    def _try_init(client_cls: type[SonarrClient] | type[RadarrClient]) -> Any:
        try:
            return client_cls()
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search(self, term: str) -> list[MediaSearchResult]:
        """
        Search both Sonarr (TV) and Radarr (movies) for a title.

        Args:
            term: Title (or partial title) to search for.

        Returns:
            Combined results, TV matches first, then movie matches.
        """
        results: list[MediaSearchResult] = []
        if self.sonarr:
            results += [self._wrap_series_search(item) for item in self.sonarr.search_series(term)]
        if self.radarr:
            results += [self._wrap_movie_search(item) for item in self.radarr.search_movies(term)]
        return results

    def get_library(self) -> list[MediaResult]:
        """Return everything currently in the Sonarr and Radarr libraries."""
        library: list[MediaResult] = []
        if self.sonarr:
            library += [self._wrap_series_result(item) for item in self.sonarr.get_library_series()]
        if self.radarr:
            library += [self._wrap_movie_result(item) for item in self.radarr.get_library_movies()]
        return library

    # ------------------------------------------------------------------
    # Adding / downloading
    # ------------------------------------------------------------------

    def add(self, result: MediaSearchResult, **kwargs: Any) -> MediaResult:
        """
        Add a search result to the correct library (Sonarr for TV, Radarr
        for movies), which triggers that system to start downloading it.

        Args:
            result: A result from search().
            **kwargs: Forwarded to SonarrClient.add_series() or
                RadarrClient.add_movie() depending on result.media_type.

        Returns:
            The added item as a MediaResult.

        Raises:
            MediaError: If the backend for this media type isn't configured.
        """
        if result.media_type == MediaType.SERIES:
            if not self.sonarr:
                raise MediaError("Sonarr is not configured (set SONARR_API_KEY in .env)")
            added = self.sonarr.add_series(result.source, **kwargs)
            return self._wrap_series_result(added)

        if not self.radarr:
            raise MediaError("Radarr is not configured (set RADARR_API_KEY in .env)")
        added = self.radarr.add_movie(result.source, **kwargs)
        return self._wrap_movie_result(added)

    def search_and_download(
        self,
        term: str,
        match_index: int = 0,
        **add_kwargs: Any,
    ) -> MediaResult:
        """
        Convenience method: search both backends for a title and add the
        chosen match.

        Args:
            term: Title to search for.
            match_index: Index into the combined search results to add
                (default: best match).
            **add_kwargs: Forwarded to add().

        Returns:
            The added item as a MediaResult.

        Raises:
            MediaError: If no matches are found, or match_index is out of range.
        """
        results = self.search(term)
        if not results:
            raise MediaError(f"No results found for '{term}'")
        if match_index >= len(results):
            raise MediaError(f"match_index {match_index} out of range, only {len(results)} results found")
        return self.add(results[match_index], **add_kwargs)

    # ------------------------------------------------------------------
    # Removing
    # ------------------------------------------------------------------

    def remove(
        self,
        media: MediaResult,
        delete_files: bool = False,
        add_exclusion: bool = False,
    ) -> None:
        """
        Remove a library item from whichever backend it belongs to.

        Args:
            media: A MediaResult, e.g. from get_library() or the return
                value of add()/search_and_download().
            delete_files: Whether to also delete the media's files from disk.
            add_exclusion: Whether to exclude the media from future
                automatic list imports.

        Raises:
            MediaError: If the backend for this media type isn't configured.
        """
        if media.media_type == MediaType.SERIES:
            if not self.sonarr:
                raise MediaError("Sonarr is not configured (set SONARR_API_KEY in .env)")
            self.sonarr.remove_series(
                media.source,
                delete_files=delete_files,
                add_import_list_exclusion=add_exclusion,
            )
            return

        if not self.radarr:
            raise MediaError("Radarr is not configured (set RADARR_API_KEY in .env)")
        self.radarr.remove_movie(
            media.source,
            delete_files=delete_files,
            add_import_exclusion=add_exclusion,
        )

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_series_search(item: SeriesSearchResult) -> MediaSearchResult:
        return MediaSearchResult(
            media_type=MediaType.SERIES,
            title=item.title,
            year=item.year,
            overview=item.overview,
            already_in_library=item.already_in_library,
            external_id=item.tvdb_id,
            poster_url=item.poster_url,
            fanart_url=item.fanart_url,
            genres=item.genres,
            runtime=item.runtime,
            rating=item.rating,
            network=item.network,
            studio=None,
            source=item,
        )

    @staticmethod
    def _wrap_movie_search(item: MovieSearchResult) -> MediaSearchResult:
        return MediaSearchResult(
            media_type=MediaType.MOVIE,
            title=item.title,
            year=item.year,
            overview=item.overview,
            already_in_library=item.already_in_library,
            external_id=item.tmdb_id,
            poster_url=item.poster_url,
            fanart_url=item.fanart_url,
            genres=item.genres,
            runtime=item.runtime,
            rating=item.rating,
            network=None,
            studio=item.studio,
            source=item,
        )

    @staticmethod
    def _wrap_series_result(item: SeriesResult) -> MediaResult:
        return MediaResult(
            media_type=MediaType.SERIES,
            id=item.id,
            title=item.title,
            monitored=item.monitored,
            external_id=item.tvdb_id,
            year=item.year,
            overview=item.overview,
            poster_url=item.poster_url,
            fanart_url=item.fanart_url,
            genres=item.genres,
            runtime=item.runtime,
            rating=item.rating,
            network=item.network,
            studio=None,
            source=item,
        )

    @staticmethod
    def _wrap_movie_result(item: MovieResult) -> MediaResult:
        return MediaResult(
            media_type=MediaType.MOVIE,
            id=item.id,
            title=item.title,
            monitored=item.monitored,
            external_id=item.tmdb_id,
            year=item.year,
            overview=item.overview,
            poster_url=item.poster_url,
            fanart_url=item.fanart_url,
            genres=item.genres,
            runtime=item.runtime,
            rating=item.rating,
            network=None,
            studio=item.studio,
            source=item,
        )


def _interactive_main() -> None:
    """Prompt for a title, list matches across both backends, and add the chosen one."""
    client = MediaClient()
    if not client.sonarr and not client.radarr:
        print("Neither Sonarr nor Radarr is configured. Set SONARR_API_KEY/RADARR_API_KEY in .env.")
        return

    term = input("Search for a TV show or movie: ").strip()
    results = client.search(term)
    if not results:
        print(f"No results found for '{term}'")
        return

    for i, item in enumerate(results):
        kind = "Series" if item.media_type == MediaType.SERIES else "Movie"
        in_library = " (already in library)" if item.already_in_library else ""
        print(f"[{i}] [{kind}] {item.title} ({item.year}){in_library}")

    choice = input("Enter the number to download (or blank to cancel): ").strip()
    if not choice:
        return

    selected = results[int(choice)]
    added = client.add(selected)
    backend = "Sonarr" if added.media_type == MediaType.SERIES else "Radarr"
    print(f"Added '{added.title}' to {backend} and started searching for downloads.")


if __name__ == "__main__":
    _interactive_main()
