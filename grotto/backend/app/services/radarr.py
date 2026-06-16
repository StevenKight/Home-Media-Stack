"""
radarr.py

Client for interacting with the Radarr v3 API to search for and download movies.

Connection settings (RADARR_HOST, RADARR_PORT, RADARR_API_KEY) are read from
the application settings (see app/config/config.py), which load them from the
environment / .env file. Set these in your .env (see .env.example) to point
at your Radarr instance, then use RadarrClient to look up movies and add them
to the library (which triggers Radarr to start downloading them).

Example:
    from app.services.radarr import RadarrClient

    client = RadarrClient()
    results = client.search_movies("The Matrix")
    for movie in results:
        print(movie.tmdb_id, movie.title, movie.year)

    client.add_movie(results[0])

Run this file directly for an interactive search-and-download prompt:
    python -m app.services.radarr
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.config import get_settings


class RadarrError(Exception):
    """Raised when the Radarr API returns an error response or an operation is invalid."""


@dataclass
class MovieSearchResult:
    """A single match from a Radarr movie lookup (not necessarily in the library yet)."""

    tmdb_id: int
    title: str
    year: int | None
    overview: str | None
    status: str | None
    studio: str | None
    already_in_library: bool
    raw: dict[str, Any]


@dataclass
class MovieResult:
    """A movie that exists in the Radarr library."""

    id: int
    tmdb_id: int
    title: str
    monitored: bool
    raw: dict[str, Any]


class RadarrClient:
    """Thin wrapper around the Radarr v3 API for searching and downloading movies."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        use_ssl: bool = False,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        host = host or settings.RADARR_HOST
        port = port or settings.RADARR_PORT
        api_key = api_key or settings.RADARR_API_KEY
        if not api_key:
            raise ValueError("Radarr API key is required (set RADARR_API_KEY in .env)")
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}/api/v3"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-Api-Key": api_key})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        response = self._session.request(method, url, timeout=self.timeout, **kwargs)
        if not response.ok:
            raise RadarrError(
                f"Radarr API request failed: {method} {path} -> {response.status_code} {response.text}"
            )
        return response.json() if response.content else None

    def test_connection(self) -> bool:
        """Verify the host, port, and API key are valid by hitting the status endpoint."""
        self._request("GET", "/system/status")
        return True

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search_movies(self, term: str) -> list[MovieSearchResult]:
        """
        Search for movies by title using Radarr's external lookup (TheMovieDB).

        Args:
            term: Movie title (or partial title) to search for.

        Returns:
            Matching movies, ordered by Radarr's relevance ranking. Movies
            already in your library are included with already_in_library=True.
        """
        data = self._request("GET", "/movie/lookup", params={"term": term})
        return [self._to_search_result(item) for item in data]

    def get_library_movies(self) -> list[MovieResult]:
        """Return all movies currently in the Radarr library."""
        data = self._request("GET", "/movie")
        return [self._to_movie_result(item) for item in data]

    def find_in_library_by_tmdb_id(self, tmdb_id: int) -> MovieResult | None:
        """Return the library entry for a given TMDB id, or None if not added yet."""
        for movie in self.get_library_movies():
            if movie.tmdb_id == tmdb_id:
                return movie
        return None

    # ------------------------------------------------------------------
    # Library configuration helpers
    # ------------------------------------------------------------------

    def get_quality_profiles(self) -> list[dict[str, Any]]:
        return self._request("GET", "/qualityprofile")

    def get_root_folders(self) -> list[dict[str, Any]]:
        return self._request("GET", "/rootfolder")

    def _default_quality_profile_id(self) -> int:
        profiles = self.get_quality_profiles()
        if not profiles:
            raise RadarrError("No quality profiles configured in Radarr")
        return profiles[0]["id"]

    def _default_root_folder_path(self) -> str:
        folders = self.get_root_folders()
        if not folders:
            raise RadarrError("No root folders configured in Radarr")
        return folders[0]["path"]

    # ------------------------------------------------------------------
    # Adding / downloading
    # ------------------------------------------------------------------

    def add_movie(
        self,
        movie: MovieSearchResult,
        quality_profile_id: int | None = None,
        root_folder_path: str | None = None,
        monitored: bool = True,
        minimum_availability: str = "released",
        search_now: bool = True,
    ) -> MovieResult:
        """
        Add a movie found via search_movies() to the Radarr library, which
        causes Radarr to monitor it and (if search_now is True) immediately
        search indexers and start downloading it.

        Args:
            movie: A result from search_movies().
            quality_profile_id: Quality profile to use. Defaults to the
                first profile configured in Radarr.
            root_folder_path: Library folder to store the movie in.
                Defaults to the first root folder configured in Radarr.
            monitored: Whether Radarr should monitor this movie.
            minimum_availability: One of "tba", "announced", "inCinemas",
                "released" (default), or "deleted" - controls how soon
                Radarr is allowed to search for/grab the movie.
            search_now: Whether to immediately search for and download
                the movie after adding.

        Returns:
            The movie record as Radarr created it in the library.

        Raises:
            RadarrError: If the movie is already in the library, or Radarr
                rejects the add request (e.g. invalid root folder/profile).
        """
        if self.find_in_library_by_tmdb_id(movie.tmdb_id):
            raise RadarrError(f"'{movie.title}' is already in the Radarr library")

        payload = dict(movie.raw)
        payload["qualityProfileId"] = quality_profile_id or self._default_quality_profile_id()
        payload["rootFolderPath"] = root_folder_path or self._default_root_folder_path()
        payload["monitored"] = monitored
        payload["minimumAvailability"] = minimum_availability
        payload["addOptions"] = {
            "monitor": "movieOnly",
            "searchForMovie": search_now,
        }

        data = self._request("POST", "/movie", json=payload)
        return self._to_movie_result(data)

    # ------------------------------------------------------------------
    # Removing
    # ------------------------------------------------------------------

    def remove_movie(
        self,
        movie: MovieResult | int,
        delete_files: bool = False,
        add_import_exclusion: bool = False,
    ) -> None:
        """
        Remove a movie from the Radarr library.

        Args:
            movie: A MovieResult (e.g. from get_library_movies()) or a raw
                Radarr movie id.
            delete_files: Whether to also delete the movie's files from disk.
            add_import_exclusion: Whether to add the movie to the import
                list exclusion list, preventing it from being re-added
                automatically by list sync.

        Raises:
            RadarrError: If Radarr rejects the delete request.
        """
        movie_id = movie.id if isinstance(movie, MovieResult) else movie
        self._request(
            "DELETE",
            f"/movie/{movie_id}",
            params={
                "deleteFiles": delete_files,
                "addImportExclusion": add_import_exclusion,
            },
        )

    def remove_movie_by_tmdb_id(
        self,
        tmdb_id: int,
        delete_files: bool = False,
        add_import_exclusion: bool = False,
    ) -> None:
        """
        Convenience method: look up a library movie by TMDB id and remove it.

        Raises:
            RadarrError: If no movie with that TMDB id is in the library.
        """
        movie = self.find_in_library_by_tmdb_id(tmdb_id)
        if not movie:
            raise RadarrError(f"No movie with tmdbId {tmdb_id} found in the Radarr library")
        self.remove_movie(movie, delete_files=delete_files, add_import_exclusion=add_import_exclusion)

    def search_and_download(
        self,
        term: str,
        match_index: int = 0,
        **add_kwargs: Any,
    ) -> MovieResult:
        """
        Convenience method: search Radarr for a title and add the chosen match.

        Args:
            term: Title to search Radarr for.
            match_index: Index into the search results to add (default: best match).
            **add_kwargs: Extra arguments forwarded to add_movie().

        Returns:
            The movie record as added to the Radarr library.

        Raises:
            RadarrError: If no matches are found for the given term, or
                match_index is out of range.
        """
        results = self.search_movies(term)
        if not results:
            raise RadarrError(f"No Radarr search results found for '{term}'")
        if match_index >= len(results):
            raise RadarrError(
                f"match_index {match_index} out of range, only {len(results)} results found"
            )
        return self.add_movie(results[match_index], **add_kwargs)

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_search_result(item: dict[str, Any]) -> MovieSearchResult:
        return MovieSearchResult(
            tmdb_id=item.get("tmdbId", 0),
            title=item.get("title", ""),
            year=item.get("year"),
            overview=item.get("overview"),
            status=item.get("status"),
            studio=item.get("studio"),
            already_in_library=bool(item.get("id")),
            raw=item,
        )

    @staticmethod
    def _to_movie_result(item: dict[str, Any]) -> MovieResult:
        return MovieResult(
            id=item.get("id", 0),
            tmdb_id=item.get("tmdbId", 0),
            title=item.get("title", ""),
            monitored=item.get("monitored", False),
            raw=item,
        )


def _interactive_main() -> None:
    """Prompt for a movie title, list matches, and add the chosen one to Radarr."""
    client = RadarrClient()
    client.test_connection()

    term = input("Search for a movie: ").strip()
    results = client.search_movies(term)
    if not results:
        print(f"No results found for '{term}'")
        return

    for i, movie in enumerate(results):
        in_library = " (already in library)" if movie.already_in_library else ""
        print(f"[{i}] {movie.title} ({movie.year}){in_library}")

    choice = input("Enter the number of the movie to download (or blank to cancel): ").strip()
    if not choice:
        return

    selected = results[int(choice)]
    added = client.add_movie(selected)
    print(f"Added '{added.title}' to Radarr and started searching for downloads.")


if __name__ == "__main__":
    _interactive_main()
