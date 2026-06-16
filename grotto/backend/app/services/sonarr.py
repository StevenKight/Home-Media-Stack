"""
sonarr.py

Client for interacting with the Sonarr v3 API to search for and download TV series.

Connection settings (SONARR_HOST, SONARR_PORT, SONARR_API_KEY) are read from
the application settings (see app/config/config.py), which load them from the
environment / .env file. Set these in your .env (see .env.example) to point
at your Sonarr instance, then use SonarrClient to look up shows and add them
to the library (which triggers Sonarr to start downloading them).

Example:
    from app.services.sonarr import SonarrClient

    client = SonarrClient()
    results = client.search_series("Breaking Bad")
    for show in results:
        print(show.tvdb_id, show.title, show.year)

    client.add_series(results[0])

Run this file directly for an interactive search-and-download prompt:
    python -m app.services.sonarr
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.config import get_settings


class SonarrError(Exception):
    """Raised when the Sonarr API returns an error response or an operation is invalid."""


@dataclass
class SeriesSearchResult:
    """A single match from a Sonarr series lookup (not necessarily in the library yet)."""

    tvdb_id: int
    title: str
    year: int | None
    overview: str | None
    status: str | None
    network: str | None
    seasons: int
    already_in_library: bool
    raw: dict[str, Any]


@dataclass
class SeriesResult:
    """A series that exists in the Sonarr library."""

    id: int
    tvdb_id: int
    title: str
    monitored: bool
    raw: dict[str, Any]


class SonarrClient:
    """Thin wrapper around the Sonarr v3 API for searching and downloading TV series."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        use_ssl: bool = False,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        host = host or settings.SONARR_HOST
        port = port or settings.SONARR_PORT
        api_key = api_key or settings.SONARR_API_KEY
        if not api_key:
            raise ValueError("Sonarr API key is required (set SONARR_API_KEY in .env)")
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}/api/v3"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-Api-Key": api_key})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        response = self._session.request(method, url, timeout=self.timeout, **kwargs)
        if not response.ok:
            raise SonarrError(
                f"Sonarr API request failed: {method} {path} -> {response.status_code} {response.text}"
            )
        return response.json() if response.content else None

    def test_connection(self) -> bool:
        """Verify the host, port, and API key are valid by hitting the status endpoint."""
        self._request("GET", "/system/status")
        return True

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search_series(self, term: str) -> list[SeriesSearchResult]:
        """
        Search for TV series by title using Sonarr's external lookup (TheTVDB).

        Args:
            term: Show title (or partial title) to search for.

        Returns:
            Matching shows, ordered by Sonarr's relevance ranking. Shows
            already in your library are included with already_in_library=True.
        """
        data = self._request("GET", "/series/lookup", params={"term": term})
        return [self._to_search_result(item) for item in data]

    def get_library_series(self) -> list[SeriesResult]:
        """Return all series currently in the Sonarr library."""
        data = self._request("GET", "/series")
        return [self._to_series_result(item) for item in data]

    def find_in_library_by_tvdb_id(self, tvdb_id: int) -> SeriesResult | None:
        """Return the library entry for a given TVDB id, or None if not added yet."""
        for series in self.get_library_series():
            if series.tvdb_id == tvdb_id:
                return series
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
            raise SonarrError("No quality profiles configured in Sonarr")
        return profiles[0]["id"]

    def _default_root_folder_path(self) -> str:
        folders = self.get_root_folders()
        if not folders:
            raise SonarrError("No root folders configured in Sonarr")
        return folders[0]["path"]

    # ------------------------------------------------------------------
    # Adding / downloading
    # ------------------------------------------------------------------

    def add_series(
        self,
        series: SeriesSearchResult,
        quality_profile_id: int | None = None,
        root_folder_path: str | None = None,
        monitored: bool = True,
        season_folder: bool = True,
        search_now: bool = True,
    ) -> SeriesResult:
        """
        Add a series found via search_series() to the Sonarr library, which
        causes Sonarr to monitor it and (if search_now is True) immediately
        search indexers and start downloading it.

        Args:
            series: A result from search_series().
            quality_profile_id: Quality profile to use. Defaults to the
                first profile configured in Sonarr.
            root_folder_path: Library folder to store the series in.
                Defaults to the first root folder configured in Sonarr.
            monitored: Whether Sonarr should monitor this series for episodes.
            season_folder: Whether to organize episodes into season subfolders.
            search_now: Whether to immediately search for and download
                missing episodes after adding.

        Returns:
            The series record as Sonarr created it in the library.

        Raises:
            SonarrError: If the series is already in the library, or Sonarr
                rejects the add request (e.g. invalid root folder/profile).
        """
        if self.find_in_library_by_tvdb_id(series.tvdb_id):
            raise SonarrError(f"'{series.title}' is already in the Sonarr library")

        payload = dict(series.raw)
        payload["qualityProfileId"] = quality_profile_id or self._default_quality_profile_id()
        payload["rootFolderPath"] = root_folder_path or self._default_root_folder_path()
        payload["monitored"] = monitored
        payload["seasonFolder"] = season_folder
        payload["addOptions"] = {
            "monitor": "all" if monitored else "none",
            "searchForMissingEpisodes": search_now,
            "searchForCutoffUnmetEpisodes": False,
        }

        data = self._request("POST", "/series", json=payload)
        return self._to_series_result(data)

    # ------------------------------------------------------------------
    # Removing
    # ------------------------------------------------------------------

    def remove_series(
        self,
        series: SeriesResult | int,
        delete_files: bool = False,
        add_import_list_exclusion: bool = False,
    ) -> None:
        """
        Remove a series from the Sonarr library.

        Args:
            series: A SeriesResult (e.g. from get_library_series()) or a raw
                Sonarr series id.
            delete_files: Whether to also delete the series' files from disk.
            add_import_list_exclusion: Whether to add the series to the
                import list exclusion list, preventing it from being
                re-added automatically by list sync.

        Raises:
            SonarrError: If Sonarr rejects the delete request.
        """
        series_id = series.id if isinstance(series, SeriesResult) else series
        self._request(
            "DELETE",
            f"/series/{series_id}",
            params={
                "deleteFiles": delete_files,
                "addImportListExclusion": add_import_list_exclusion,
            },
        )

    def remove_series_by_tvdb_id(
        self,
        tvdb_id: int,
        delete_files: bool = False,
        add_import_list_exclusion: bool = False,
    ) -> None:
        """
        Convenience method: look up a library series by TVDB id and remove it.

        Raises:
            SonarrError: If no series with that TVDB id is in the library.
        """
        series = self.find_in_library_by_tvdb_id(tvdb_id)
        if not series:
            raise SonarrError(f"No series with tvdbId {tvdb_id} found in the Sonarr library")
        self.remove_series(series, delete_files=delete_files, add_import_list_exclusion=add_import_list_exclusion)

    def search_and_download(
        self,
        term: str,
        match_index: int = 0,
        **add_kwargs: Any,
    ) -> SeriesResult:
        """
        Convenience method: search Sonarr for a title and add the chosen match.

        Args:
            term: Title to search Sonarr for.
            match_index: Index into the search results to add (default: best match).
            **add_kwargs: Extra arguments forwarded to add_series().

        Returns:
            The series record as added to the Sonarr library.

        Raises:
            SonarrError: If no matches are found for the given term, or
                match_index is out of range.
        """
        results = self.search_series(term)
        if not results:
            raise SonarrError(f"No Sonarr search results found for '{term}'")
        if match_index >= len(results):
            raise SonarrError(
                f"match_index {match_index} out of range, only {len(results)} results found"
            )
        return self.add_series(results[match_index], **add_kwargs)

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_search_result(item: dict[str, Any]) -> SeriesSearchResult:
        return SeriesSearchResult(
            tvdb_id=item.get("tvdbId", 0),
            title=item.get("title", ""),
            year=item.get("year"),
            overview=item.get("overview"),
            status=item.get("status"),
            network=item.get("network"),
            seasons=len(item.get("seasons") or []),
            already_in_library=bool(item.get("id")),
            raw=item,
        )

    @staticmethod
    def _to_series_result(item: dict[str, Any]) -> SeriesResult:
        return SeriesResult(
            id=item.get("id", 0),
            tvdb_id=item.get("tvdbId", 0),
            title=item.get("title", ""),
            monitored=item.get("monitored", False),
            raw=item,
        )


def _interactive_main() -> None:
    """Prompt for a show title, list matches, and add the chosen one to Sonarr."""
    client = SonarrClient()
    client.test_connection()

    term = input("Search for a TV show: ").strip()
    results = client.search_series(term)
    if not results:
        print(f"No results found for '{term}'")
        return

    for i, show in enumerate(results):
        in_library = " (already in library)" if show.already_in_library else ""
        print(f"[{i}] {show.title} ({show.year}){in_library}")

    choice = input("Enter the number of the show to download (or blank to cancel): ").strip()
    if not choice:
        return

    selected = results[int(choice)]
    added = client.add_series(selected)
    print(f"Added '{added.title}' to Sonarr and started searching for downloads.")


if __name__ == "__main__":
    _interactive_main()
