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
import ssl
import os
import json

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
        
        # Create SSL context for secure connections
        self.ssl_context = ssl.create_default_context()
        # Allow connections to sites with self-signed certificates (for development)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
                # JSearch API configuration (OpenWebNinja for production-quality job data)
        self.jsearch_api_key = os.getenv('JSEARCH_API_KEY')
        self.jsearch_base_url = "https://api.openwebninja.com/jsearch/search"
        self.use_jsearch = bool(self.jsearch_api_key)  # Use JSearch if API key is available
    
    async def search_jobs(
        self,
        job_title: str,
        location: str = "remote OR us",
        date_posted: str = "posted today",
        sources: List[str] = ["workday"],
        max_results: int = 20,
        employment_types: List[str] = None,
        experience_level: str = "",
        work_from_home: bool = False,
        salary_min: int = None,
        salary_max: int = None
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
        
        # If JSearch API is available, use it as primary source
        if self.use_jsearch:
            try:
                jsearch_jobs = await self._search_jsearch(job_title, location, date_posted, max_results, employment_types, experience_level, work_from_home)
                if jsearch_jobs:
                    logger.info(f"[JOB_SEARCH] JSearch API returned {len(jsearch_jobs)} jobs")
                    return jsearch_jobs[:max_results]
            except Exception as e:
                logger.error(f"[JOB_SEARCH] JSearch API failed: {e}, falling back to other sources")
        
        # Try Greenhouse API as secondary source (high-quality tech jobs)
        try:
            greenhouse_jobs = await self._search_greenhouse_companies(job_title, location, max_results)
            if greenhouse_jobs:
                logger.info(f"[JOB_SEARCH] Greenhouse API returned {len(greenhouse_jobs)} jobs")
                return greenhouse_jobs[:max_results]
        except Exception as e:
            logger.error(f"[JOB_SEARCH] Greenhouse API failed: {e}, falling back to scraping")
        
        all_jobs = []
        
        # Search each source concurrently (fallback method)
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
    
    async def _search_jsearch(
        self,
        job_title: str,
        location: str,
        date_posted: str,
        max_results: int,
        employment_types: List[str] = None,
        experience_level: str = "",
        work_from_home: bool = False
    ) -> List[Dict]:
        """
        Search jobs using JSearch API (RapidAPI)
        Professional job search with real, up-to-date results
        """
        try:
            # Parse location for JSearch API format
            if "remote" in location.lower():
                country = "US"  # Default to US for remote jobs
                radius = "100"
            else:
                country = "US"  # Can be enhanced to detect country from location
                radius = "25"   # 25 mile radius
            
            # Map date_posted to JSearch format
            date_posted_mapping = {
                "posted today": "today",
                "posted this week": "3days", 
                "posted this month": "week",
                "": "all"
            }
            date_posted_param = date_posted_mapping.get(date_posted.lower(), "week")
            
            # JSearch API parameters
            params = {
                "query": f"{job_title} {location}",
                "page": "1",
                "num_pages": "1", 
                "country": country,
                "date_posted": date_posted_param,
                "radius": radius,
                "work_from_home": str(work_from_home).lower()
            }
            
            # Add employment types if specified
            if employment_types:
                params["employment_types"] = ",".join(employment_types)
            
            # Add experience level if specified
            if experience_level:
                params["job_requirements"] = experience_level
            
            headers = {
                "x-api-key": self.jsearch_api_key
            }
            
            logger.info(f"[JSEARCH] Searching: {params['query']}")
            
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=self.ssl_context)
            ) as session:
                async with session.get(self.jsearch_base_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"[JSEARCH] API returned status: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    # OpenWebNinja API returns data directly in 'data' field
                    if 'data' not in data:
                        logger.error(f"[JSEARCH] API response missing data field: {data}")
                        return []
                    
                    jobs_data = data.get('data', [])
                    jobs = []
                    
                    for job_data in jobs_data[:max_results]:
                        try:
                            # Format job data to match our schema
                            job = {
                                'title': job_data.get('job_title', 'Unknown Title'),
                                'company': job_data.get('employer_name', 'Unknown Company'),
                                'location': job_data.get('job_city', '') + ', ' + job_data.get('job_state', '') if job_data.get('job_city') else job_data.get('job_country', 'Unknown Location'),
                                'link': job_data.get('job_apply_link') or job_data.get('job_url', ''),
                                'snippet': job_data.get('job_description', '')[:200] + '...' if job_data.get('job_description') else 'No description available',
                                'source': 'JSearch API',
                                # Additional JSearch-specific data
                                'salary_min': job_data.get('job_min_salary'),
                                'salary_max': job_data.get('job_max_salary'),
                                'employment_type': job_data.get('job_employment_type', 'Not specified'),
                                'posted_date': job_data.get('job_posted_at_datetime_utc'),
                                'is_remote': job_data.get('job_is_remote', False),
                                'job_id': job_data.get('job_id')
                            }
                            jobs.append(job)
                        except Exception as e:
                            logger.warning(f"[JSEARCH] Failed to parse job data: {e}")
                            continue
                    
                    logger.info(f"[JSEARCH] Successfully parsed {len(jobs)} jobs")
                    return jobs
        
        except Exception as e:
            logger.error(f"[JSEARCH] Search failed: {e}")
            return []
    
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
            logger.debug(f"[GOOGLE_SEARCH] Searching: {search_url}")
            
            async with aiohttp.ClientSession(timeout=self.timeout, connector=aiohttp.TCPConnector(ssl=self.ssl_context)) as session:
                async with session.get(search_url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.warning(f"[GOOGLE_SEARCH] Non-200 status: {response.status}")
                        return []
                    
                    html = await response.text()
                    logger.debug(f"[GOOGLE_SEARCH] Response length: {len(html)} chars")
                    
                    # Check if Google is blocking us
                    if "Our systems have detected unusual traffic" in html or "blocked" in html.lower():
                        logger.warning("[GOOGLE_SEARCH] Google detected unusual traffic - likely blocked")
                        return []
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Debug: Check if we found any result divs
                    result_divs = soup.select('div.g')
                    logger.debug(f"[GOOGLE_SEARCH] Found {len(result_divs)} result divs")
                    
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
                    
                    # If no jobs found and this might be due to Google blocking, return sample jobs for demo
                    if not jobs and len(html) < 5000:  # Suspiciously small response
                        logger.info("[GOOGLE_SEARCH] Returning sample jobs due to potential blocking")
                        return self._get_sample_jobs(query)
                    
                    return jobs
        
        except asyncio.TimeoutError:
            logger.error("[GOOGLE_SEARCH] Request timed out")
            return self._get_sample_jobs(query)  # Fallback to sample jobs
        except Exception as e:
            logger.error(f"[GOOGLE_SEARCH] Error: {e}")
            return self._get_sample_jobs(query)  # Fallback to sample jobs
    
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
    
    def _get_sample_jobs(self, query: str) -> List[Dict]:
        """
        Returns sample job data when scraping fails
        Useful for development and demo purposes
        """
        job_title_from_query = query.split('"')[1] if '"' in query else "Software Engineer"
        
        sample_jobs = [
            {
                'title': f'Senior {job_title_from_query}',
                'company': 'TechCorp Inc.',
                'location': 'Remote',
                'link': 'https://example-jobs.com/senior-position',
                'snippet': f'We are looking for an experienced {job_title_from_query} to join our growing team. Remote work available.',
                'source': 'Demo'
            },
            {
                'title': f'{job_title_from_query} - Full Stack',
                'company': 'InnovateLabs',
                'location': 'San Francisco, CA',
                'link': 'https://example-jobs.com/fullstack-position',
                'snippet': f'Join our innovative team as a {job_title_from_query}. Competitive salary and benefits package.',
                'source': 'Demo'
            },
            {
                'title': f'Lead {job_title_from_query}',
                'company': 'DataDriven Solutions',
                'location': 'New York, NY',
                'link': 'https://example-jobs.com/lead-position',
                'snippet': f'Leading {job_title_from_query} position available. Great opportunity for career growth.',
                'source': 'Demo'
            }
        ]
        
        logger.info(f"[SAMPLE_JOBS] Returning {len(sample_jobs)} demo jobs for query: {query}")
        return sample_jobs

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

    async def _search_greenhouse_companies(
        self,
        job_title: str,
        location: str = "",
        max_results: int = 20,
        company_tokens: List[str] = None
    ) -> List[Dict]:
        """
        Search jobs from Greenhouse API across multiple company boards
        
        Args:
            job_title: Job title to search for
            location: Location filter (optional)
            max_results: Maximum number of results to return
            company_tokens: List of company tokens to search (defaults to popular tech companies)
        """
        if not company_tokens:
            # Popular tech companies using Greenhouse
            company_tokens = [
                "databricks", "stripe", "snowflake", "nvidia", "tiktok", 
                "canva", "instacart", "doordash", "coinbase", "robinhood",
                "discord", "figma", "notion", "airtable", "palantir",
                "datadog", "elastic", "mongodb", "redis", "confluent"
            ]
        
        all_jobs = []
        
        try:
            # Create SSL context for HTTPS requests
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                # Create tasks for each company
                tasks = []
                for company_token in company_tokens[:10]:  # Limit to 10 companies to avoid rate limits
                    task = self._fetch_greenhouse_company_jobs(session, company_token, job_title, location)
                    tasks.append(task)
                
                # Execute requests concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for company_jobs in results:
                    if isinstance(company_jobs, list):
                        all_jobs.extend(company_jobs)
                        if len(all_jobs) >= max_results:
                            break
                    elif isinstance(company_jobs, Exception):
                        logger.warning(f"[GREENHOUSE] Error fetching jobs: {company_jobs}")
            
            # Sort by updated date (most recent first)
            all_jobs.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            
            logger.info(f"[GREENHOUSE] Found {len(all_jobs)} jobs across {len(company_tokens)} companies")
            return all_jobs[:max_results]
            
        except Exception as e:
            logger.error(f"[GREENHOUSE] API search failed: {e}")
            return []

    async def _fetch_greenhouse_company_jobs(
        self,
        session: aiohttp.ClientSession,
        company_token: str,
        job_title: str,
        location: str = ""
    ) -> List[Dict]:
        """
        Fetch jobs from a specific Greenhouse company board
        """
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_token}/jobs"
            params = {
                "content": "true",  # Include full job descriptions
                "active": "true"    # Only active jobs
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    jobs = data.get("jobs", [])
                    
                    # Filter jobs by title and location
                    filtered_jobs = []
                    for job in jobs:
                        title = job.get("title", "").lower()
                        job_location = job.get("location", {}).get("name", "").lower() if job.get("location") else ""
                        
                        # Check if job title matches
                        title_match = any(keyword.lower() in title for keyword in job_title.split())
                        
                        # Check location filter if specified
                        location_match = True
                        if location and location.lower() != "remote":
                            location_match = (
                                location.lower() in job_location or
                                "remote" in job_location or
                                "anywhere" in job_location
                            )
                        
                        if title_match and location_match:
                            # Normalize job data
                            normalized_job = {
                                "title": job.get("title", ""),
                                "company": company_token.replace("-", " ").title(),
                                "location": job.get("location", {}).get("name", "") if job.get("location") else "Not specified",
                                "url": job.get("absolute_url", ""),
                                "description": self._clean_html_description(job.get("content", "")),
                                "department": job.get("departments", [{}])[0].get("name", "") if job.get("departments") else "",
                                "updated_at": job.get("updated_at", ""),
                                "job_id": str(job.get("id", "")),
                                "source": "Greenhouse",
                                "employment_type": "Full-time",  # Greenhouse typically posts full-time roles
                                "salary": "Not specified"
                            }
                            filtered_jobs.append(normalized_job)
                    
                    logger.debug(f"[GREENHOUSE] {company_token}: {len(filtered_jobs)} matching jobs")
                    return filtered_jobs
                else:
                    logger.warning(f"[GREENHOUSE] {company_token}: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.warning(f"[GREENHOUSE] Error fetching {company_token}: {e}")
            return []

    def _clean_html_description(self, html_content: str) -> str:
        """
        Clean HTML content to extract plain text description
        """
        if not html_content:
            return ""
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            # Get text and clean up whitespace
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text[:1000] + "..." if len(text) > 1000 else text
        except:
            # Fallback: simple HTML tag removal
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            return text[:1000] + "..." if len(text) > 1000 else text

# Global instance
job_scraper = JobScraper()
