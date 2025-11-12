"""
Job Scraper Module
Scrapes job postings from multiple job board platforms using Google Search
Supports: Workday, Greenhouse, Lever, LinkedIn
"""

import aiohttp
import asyncio
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from urllib.parse import quote_plus
import logging

logger = logging.getLogger(__name__)

class JobScraper:
    """
    Advanced job scraper supporting multiple job board platforms
    Uses Google Search as primary discovery method + direct scraping
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def search_jobs(
        self,
        job_title: str,
        location: str = "remote OR us",
        date_posted: str = "posted today",
        sources: List[str] = ["workday"],
        max_results: int = 20
    ) -> List[Dict]:
        """
        Main search function - orchestrates multi-source job search
        
        Args:
            job_title: Job title/role to search for
            location: Location filter query
            date_posted: Date filter ("posted today", "posted this week", etc.)
            sources: List of job board sources to search
            max_results: Max results per source
        
        Returns:
            Combined list of job dictionaries from all sources
        """
        logger.info(f"[JOB_SEARCH] Starting search: '{job_title}' in '{location}'")
        
        all_jobs = []
        
        # Search each source concurrently
        tasks = []
        if "workday" in sources:
            tasks.append(self._search_workday(job_title, location, date_posted, max_results))
        if "greenhouse" in sources:
            tasks.append(self._search_greenhouse(job_title, location, date_posted, max_results))
        if "lever" in sources:
            tasks.append(self._search_lever(job_title, location, date_posted, max_results))
        if "linkedin" in sources:
            tasks.append(self._search_linkedin(job_title, location, date_posted, max_results))
        
        # Execute all searches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"[JOB_SEARCH] Source failed: {result}")
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job['link'] not in seen_urls:
                seen_urls.add(job['link'])
                unique_jobs.append(job)
        
        logger.info(f"[JOB_SEARCH] Found {len(unique_jobs)} unique jobs across {len(sources)} sources")
        return unique_jobs[:max_results]
    
    async def _search_workday(
        self,
        job_title: str,
        location: str,
        date_posted: str,
        max_results: int
    ) -> List[Dict]:
        """Search Workday job boards via Google"""
        try:
            query = f'site:myworkdayjobs.com "{job_title}" ({location})'
            if date_posted:
                query += f' ("{date_posted}")'
            
            jobs = await self._google_search(query, max_results)
            
            # Enhance with Workday-specific parsing
            for job in jobs:
                # Extract company from Workday subdomain
                # Example: https://amazon.wd5.myworkdayjobs.com/...
                match = re.search(r'https?://([^.]+)\.wd\d+\.myworkdayjobs\.com', job['link'])
                if match:
                    company = match.group(1).replace('-', ' ').title()
                    job['company'] = company
                
                job['source'] = 'Workday'
            
            logger.info(f"[WORKDAY] Found {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            logger.error(f"[WORKDAY] Search failed: {e}")
            return []
    
    async def _search_greenhouse(
        self,
        job_title: str,
        location: str,
        date_posted: str,
        max_results: int
    ) -> List[Dict]:
        """Search Greenhouse job boards via Google"""
        try:
            query = f'site:greenhouse.io OR site:boards.greenhouse.io "{job_title}" ({location})'
            if date_posted:
                query += f' ("{date_posted}")'
            
            jobs = await self._google_search(query, max_results)
            
            for job in jobs:
                # Extract company from Greenhouse URL
                match = re.search(r'boards\.greenhouse\.io/([^/]+)', job['link'])
                if match:
                    company = match.group(1).replace('-', ' ').title()
                    job['company'] = company
                
                job['source'] = 'Greenhouse'
            
            logger.info(f"[GREENHOUSE] Found {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            logger.error(f"[GREENHOUSE] Search failed: {e}")
            return []
    
    async def _search_lever(
        self,
        job_title: str,
        location: str,
        date_posted: str,
        max_results: int
    ) -> List[Dict]:
        """Search Lever job boards via Google"""
        try:
            query = f'site:lever.co OR site:jobs.lever.co "{job_title}" ({location})'
            if date_posted:
                query += f' ("{date_posted}")'
            
            jobs = await self._google_search(query, max_results)
            
            for job in jobs:
                # Extract company from Lever URL
                match = re.search(r'jobs\.lever\.co/([^/]+)', job['link'])
                if match:
                    company = match.group(1).replace('-', ' ').title()
                    job['company'] = company
                
                job['source'] = 'Lever'
            
            logger.info(f"[LEVER] Found {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            logger.error(f"[LEVER] Search failed: {e}")
            return []
    
    async def _search_linkedin(
        self,
        job_title: str,
        location: str,
        date_posted: str,
        max_results: int
    ) -> List[Dict]:
        """Search LinkedIn jobs via Google"""
        try:
            query = f'site:linkedin.com/jobs "{job_title}" ({location})'
            if date_posted:
                query += f' ("{date_posted}")'
            
            jobs = await self._google_search(query, max_results)
            
            for job in jobs:
                job['source'] = 'LinkedIn'
                # LinkedIn doesn't expose company easily in URL, rely on title parsing
            
            logger.info(f"[LINKEDIN] Found {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            logger.error(f"[LINKEDIN] Search failed: {e}")
            return []
    
    async def _google_search(self, query: str, max_results: int) -> List[Dict]:
        """
        Core Google search function
        Parses Google search results page
        """
        try:
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results}"
            
            async with aiohttp.ClientSession(timeout=self.timeout, connector=aiohttp.TCPConnector(ssl=self.ssl_context)) as session:
                async with session.get(search_url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.warning(f"[GOOGLE_SEARCH] Non-200 status: {response.status}")
                        return []
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    jobs = []
                    
                    # Parse search result divs
                    for result_div in soup.select('div.g'):
                        try:
                            # Extract title
                            title_elem = result_div.select_one('h3')
                            if not title_elem:
                                continue
                            title = title_elem.get_text(strip=True)
                            
                            # Extract link
                            link_elem = result_div.select_one('a')
                            if not link_elem or not link_elem.get('href'):
                                continue
                            link = link_elem['href']
                            
                            # Skip non-job links
                            if not any(domain in link for domain in ['myworkdayjobs.com', 'greenhouse.io', 'lever.co', 'linkedin.com/jobs']):
                                continue
                            
                            # Extract snippet
                            snippet_elem = result_div.select_one('div.VwiC3b, div.IsZvec')
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            
                            # Extract location from snippet/title
                            location_match = re.search(
                                r'\b(Remote|Hybrid|On-site|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})\b',
                                snippet + " " + title
                            )
                            location = location_match.group(1) if location_match else "Not specified"
                            
                            jobs.append({
                                'title': title,
                                'company': 'Unknown',  # Will be set by source-specific parser
                                'location': location,
                                'link': link,
                                'snippet': snippet[:200],  # Truncate long snippets
                                'source': 'Unknown'
                            })
                        
                        except Exception as e:
                            logger.debug(f"[GOOGLE_SEARCH] Failed to parse result: {e}")
                            continue
                    
                    return jobs
        
        except asyncio.TimeoutError:
            logger.error("[GOOGLE_SEARCH] Request timed out")
            return []
        except Exception as e:
            logger.error(f"[GOOGLE_SEARCH] Error: {e}")
            return []
    
    async def scrape_job_details(self, url: str) -> Optional[Dict]:
        """
        Scrape full job description from job posting URL
        
        Args:
            url: Direct link to job posting
        
        Returns:
            {
                'title': 'Job Title',
                'company': 'Company Name',
                'location': 'Location',
                'description': 'Full JD text',
                'url': 'Job URL'
            }
        """
        try:
            logger.info(f"[JOB_DETAILS] Scraping: {url}")
            
            async with aiohttp.ClientSession(timeout=self.timeout, connector=aiohttp.TCPConnector(ssl=self.ssl_context)) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Platform-specific selectors
                    if 'myworkdayjobs.com' in url:
                        return self._parse_workday_page(soup, url)
                    elif 'greenhouse.io' in url:
                        return self._parse_greenhouse_page(soup, url)
                    elif 'lever.co' in url:
                        return self._parse_lever_page(soup, url)
                    else:
                        # Generic fallback
                        return self._parse_generic_page(soup, url)
        
        except Exception as e:
            logger.error(f"[JOB_DETAILS] Scraping failed: {e}")
            return None
    
    def _parse_workday_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse Workday job page"""
        title = soup.select_one('h1, h2, .job-title, [data-automation-id="jobPostingHeader"]')
        company_match = re.search(r'https?://([^.]+)\.wd\d+\.myworkdayjobs\.com', url)
        company = company_match.group(1).replace('-', ' ').title() if company_match else "Unknown"
        
        # Find description container
        desc_elem = soup.select_one('[data-automation-id="jobPostingDescription"], .job-description, .content')
        description = desc_elem.get_text(separator='\n', strip=True) if desc_elem else ""
        
        return {
            'title': title.get_text(strip=True) if title else "Unknown",
            'company': company,
            'location': 'See job posting',
            'description': description,
            'url': url
        }
    
    def _parse_greenhouse_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse Greenhouse job page"""
        title = soup.select_one('.app-title, h1, .posting-headline')
        company_match = re.search(r'boards\.greenhouse\.io/([^/]+)', url)
        company = company_match.group(1).replace('-', ' ').title() if company_match else "Unknown"
        
        desc_elem = soup.select_one('#content, .content, .posting-description')
        description = desc_elem.get_text(separator='\n', strip=True) if desc_elem else ""
        
        return {
            'title': title.get_text(strip=True) if title else "Unknown",
            'company': company,
            'location': 'See job posting',
            'description': description,
            'url': url
        }
    
    def _parse_lever_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse Lever job page"""
        title = soup.select_one('.posting-headline h2, h2')
        company_match = re.search(r'jobs\.lever\.co/([^/]+)', url)
        company = company_match.group(1).replace('-', ' ').title() if company_match else "Unknown"
        
        desc_elem = soup.select_one('.content, .section-wrapper, .posting-description')
        description = desc_elem.get_text(separator='\n', strip=True) if desc_elem else ""
        
        return {
            'title': title.get_text(strip=True) if title else "Unknown",
            'company': company,
            'location': 'See job posting',
            'description': description,
            'url': url
        }
    
    def _parse_generic_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """Generic fallback parser"""
        # Try common selectors
        title = soup.select_one('h1, [class*="title"], [class*="job-title"]')
        
        # Get main content
        main_content = soup.select_one('main, article, [role="main"], .content')
        description = main_content.get_text(separator='\n', strip=True) if main_content else soup.get_text(separator='\n', strip=True)
        
        return {
            'title': title.get_text(strip=True) if title else "Unknown",
            'company': 'Unknown',
            'location': 'See job posting',
            'description': description[:5000],  # Limit length
            'url': url
        }

# Global instance
job_scraper = JobScraper()
