import re
import time
import logging
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
import urllib3

# Suppress InsecureRequestWarning if university SSL has verification quirks
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class SectionInfo:
    college: str
    course_id: str
    course_name: str
    section: str
    instructor: str
    capacity: int
    enrolled: int
    available_seats: int
    is_full: bool
    days: str
    time_from: str
    time_to: str
    room: str
    notes: str

    def to_dict(self):
        return asdict(self)


class MutahFetcher:
    """
    Reverse-engineered HTTP scraper for Mutah University Course Registration Portal:
    https://subp.mutah.edu.jo/

    Handles Barracuda WAF cookies and ASP.NET WebForms ViewState tokens.
    """

    def __init__(
        self,
        base_url: str = "https://subp.mutah.edu.jo/",
        timeout: int = 25,
        session_ttl: int = 300,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session_ttl = session_ttl

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
                "Origin": self.base_url.rstrip("/"),
                "Referer": self.base_url,
            }
        )

        self._viewstate: Optional[str] = None
        self._viewstategenerator: Optional[str] = None
        self._eventvalidation: Optional[str] = None
        self._last_refresh_time: float = 0.0

    def _is_session_expired(self) -> bool:
        if not self._viewstate or not self._eventvalidation:
            return True
        return (time.time() - self._last_refresh_time) > self.session_ttl

    def refresh_session(self) -> bool:
        """
        Performs initial GET to obtain WAF cookies and ASP.NET ViewState tokens.
        """
        logger.info("Refreshing Mutah portal session and tokens...")
        try:
            resp = self.session.get(
                self.base_url,
                timeout=self.timeout,
                verify=False,
            )
            resp.raise_for_status()
            html = resp.text

            vs_match = re.search(r'id="__VIEWSTATE"\s+value="([^"]+)"', html)
            if not vs_match:
                vs_match = re.search(r'__VIEWSTATE[^>]+value="([^"]+)"', html)

            vsg_match = re.search(r'id="__VIEWSTATEGENERATOR"\s+value="([^"]+)"', html)
            if not vsg_match:
                vsg_match = re.search(r'__VIEWSTATEGENERATOR[^>]+value="([^"]+)"', html)

            ev_match = re.search(r'id="__EVENTVALIDATION"\s+value="([^"]+)"', html)
            if not ev_match:
                ev_match = re.search(r'__EVENTVALIDATION[^>]+value="([^"]+)"', html)

            if not vs_match or not ev_match:
                logger.error("Failed to extract __VIEWSTATE or __EVENTVALIDATION from portal response.")
                return False

            self._viewstate = vs_match.group(1)
            self._viewstategenerator = vsg_match.group(1) if vsg_match else ""
            self._eventvalidation = ev_match.group(1)
            self._last_refresh_time = time.time()

            logger.info("Successfully refreshed portal session tokens.")
            return True

        except Exception as e:
            logger.error(f"Error during refresh_session: {e}")
            return False

    def _update_tokens_from_response(self, html: str) -> None:
        """Update tokens if the POST response provides fresh ones."""
        vs_match = re.search(r'__VIEWSTATE[^>]+value="([^"]+)"', html)
        if vs_match:
            self._viewstate = vs_match.group(1)
        vsg_match = re.search(r'__VIEWSTATEGENERATOR[^>]+value="([^"]+)"', html)
        if vsg_match:
            self._viewstategenerator = vsg_match.group(1)
        ev_match = re.search(r'__EVENTVALIDATION[^>]+value="([^"]+)"', html)
        if ev_match:
            self._eventvalidation = ev_match.group(1)
        self._last_refresh_time = time.time()

    def _safe_int(self, text: str) -> int:
        clean = re.sub(r"[^\d]", "", text or "")
        return int(clean) if clean else 0

    def parse_table_rows(self, html: str) -> List[SectionInfo]:
        """
        Parses GridView1 table from HTML response into SectionInfo objects.
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "GridView1"})
        if not table:
            # Fallback regex search if ID format varies slightly
            table = soup.find("table", id=re.compile(r"GridView1", re.I))

        if not table:
            logger.debug("No GridView1 table found in response.")
            return []

        results: List[SectionInfo] = []
        rows = table.find_all("tr")
        if not rows:
            return []

        # Row 0 is header
        for row in rows[1:]:
            cols = row.find_all(["td", "th"])
            if len(cols) < 11:
                continue

            col_texts = [c.get_text(strip=True) for c in cols]

            college = col_texts[0]
            course_id = col_texts[1]
            course_name = col_texts[2]
            section = col_texts[3]
            instructor = col_texts[4]
            capacity = self._safe_int(col_texts[5])
            enrolled = self._safe_int(col_texts[6])
            days = col_texts[7]
            time_from = col_texts[8]
            time_to = col_texts[9]
            room = col_texts[10]
            notes = col_texts[11] if len(col_texts) > 11 else ""

            available_seats = max(0, capacity - enrolled)

            # Check full status via row style or seat calculation
            row_style = row.get("style", "").lower()
            is_red_style = "color:red" in row_style or "color: red" in row_style
            is_full = is_red_style or (available_seats <= 0)

            section_obj = SectionInfo(
                college=college,
                course_id=course_id,
                course_name=course_name,
                section=section,
                instructor=instructor,
                capacity=capacity,
                enrolled=enrolled,
                available_seats=available_seats,
                is_full=is_full,
                days=days,
                time_from=time_from,
                time_to=time_to,
                room=room,
                notes=notes,
            )
            results.append(section_obj)

        return results

    def search_course(
        self,
        course_id: str,
        section_no: Optional[str] = None,
        retry_on_expire: bool = True,
    ) -> List[SectionInfo]:
        """
        Searches the portal for a given course number and optional section number.
        Returns a list of matching SectionInfo objects.
        """
        if self._is_session_expired():
            success = self.refresh_session()
            if not success:
                logger.error("Could not initialize session for search.")
                return []

        # Normalize inputs: clean whitespace
        clean_course = str(course_id).strip()
        clean_section = str(section_no).strip() if section_no is not None else ""

        payload = {
            "__VIEWSTATE": self._viewstate or "",
            "__VIEWSTATEGENERATOR": self._viewstategenerator or "",
            "__EVENTVALIDATION": self._eventvalidation or "",
            "lstSearchCol": "0",
            "txtSearchSubID": clean_course,
            "txtSearchSubName": "",
            "txtSearchSection": clean_section,
            "txtSearchTeacher": "",
            "ImageButton1.x": "10",
            "ImageButton1.y": "10",
        }

        try:
            resp = self.session.post(
                self.base_url,
                data=payload,
                timeout=self.timeout,
                verify=False,
            )
            resp.raise_for_status()
            html = resp.text

            # Update tokens for subsequent requests
            self._update_tokens_from_response(html)

            # Parse results
            sections = self.parse_table_rows(html)

            # If section_no was specified, filter accurately
            if clean_section:
                sections = [s for s in sections if s.section == clean_section]

            return sections

        except Exception as e:
            logger.warning(f"Error querying course {clean_course} sec {clean_section}: {e}")
            if retry_on_expire:
                logger.info("Retrying with a fresh session...")
                self.refresh_session()
                return self.search_course(course_id, section_no, retry_on_expire=False)
            return []

    def get_section(self, course_id: str, section_no: str) -> Optional[SectionInfo]:
        """
        Fetches a specific section. Returns SectionInfo or None if not found.
        """
        results = self.search_course(course_id=course_id, section_no=section_no)
        for s in results:
            if s.course_id == str(course_id).strip() and s.section == str(section_no).strip():
                return s
        return results[0] if results else None

    @property
    def lock(self) -> asyncio.Lock:
        if not hasattr(self, "_lock") or self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # Async wrappers for non-blocking I/O protected with async lock to prevent race conditions
    async def search_course_async(
        self, course_id: str, section_no: Optional[str] = None
    ) -> List[SectionInfo]:
        async with self.lock:
            return await asyncio.to_thread(self.search_course, course_id, section_no)

    async def get_section_async(
        self, course_id: str, section_no: str
    ) -> Optional[SectionInfo]:
        async with self.lock:
            return await asyncio.to_thread(self.get_section, course_id, section_no)
