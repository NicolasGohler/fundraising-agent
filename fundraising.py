from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import User
from telethon.errors import FloodWaitError
from dotenv import load_dotenv
import time
import requests
import re
from urllib.parse import urlparse
import json
import os

load_dotenv()

# Configuration
MAX_PROJECTS = 15 # Maximum projects to collect from each source (reduced by 10%)

# Apollo.io API Configuration
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APOLLO_API_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
APOLLO_BULK_ENRICHMENT_URL = "https://api.apollo.io/api/v1/people/bulk_match"

# Telegram API Configuration
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION")

def get_projects_from_cryptorank():
    """Fetch projects from CryptoRank funding rounds

    Note: CryptoRank uses Cloudflare bot protection which may block automated access.
    This function implements graceful degradation - if blocked, it returns an empty list
    and the script continues with other data sources.
    """
    url = "https://cryptorank.io/funding-rounds"
    print(f"\n{'='*60}")
    print(f" SOURCE 1: Fetching projects from CryptoRank")
    print(f"{'='*60}")

    try:
        # Try to import playwright-stealth for better detection evasion
        try:
            from playwright_stealth import Stealth
            use_stealth = True
        except ImportError:
            use_stealth = False

        with sync_playwright() as p:
            # Launch browser with anti-detection settings
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )

            page = context.new_page()

            # Apply stealth if available
            if use_stealth:
                stealth = Stealth()
                stealth.apply_stealth_sync(page)
                print(" ℹ Using stealth mode")

            # Set longer timeout for page navigation
            page.set_default_timeout(60000) # 60 seconds

            print(" Loading page...")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    print(" Page loaded successfully")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        print(f" Attempt {attempt + 1} failed: {str(e)}")
                        print(f" Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f" All {max_retries} attempts failed: {str(e)}")
                        browser.close()
                        return [] # Graceful degradation

            # Wait for potential Cloudflare challenge to resolve
            print(" Waiting for page to fully render...")
            time.sleep(10)

            # Check for Cloudflare challenge
            content = page.content()
            if "Verify you are human" in content or "Just a moment" in content or "challenge" in content[:2000].lower():
                print(" CryptoRank is protected by Cloudflare bot detection")
                print(" ℹ Skipping CryptoRank - will continue with other data sources")
                browser.close()
                return [] # Graceful degradation

            print(" Waiting for table rows to load...")
            try:
                page.wait_for_selector("a[href*='/ico/']", timeout=15000)
                print(" Found project links!")
            except Exception as e:
                # Try alternative selectors
                try:
                    page.wait_for_selector("a[href*='/price/']", timeout=10000)
                    print(" Found project links (via price URLs)!")
                except:
                    print(f" Timeout waiting for project links")
                    print(" The page structure may have changed or content is blocked")

            time.sleep(5)
            print(" Waited additional 5 seconds for complete rendering")

            print("\n Searching for project links using Playwright...")

            # Try multiple selectors to find project links
            project_links = page.locator("a[href*='/ico/']").all()
            if not project_links:
                project_links = page.locator("a[href*='/price/']").all()

            print(f" Found {len(project_links)} potential project links")

            # If no links found, check if we're still being blocked
            if len(project_links) == 0:
                total_links = len(page.locator("a").all())
                if total_links < 10:
                    print(" Very few links on page - likely still blocked by Cloudflare")
                    print(" ℹ Skipping CryptoRank - will continue with other data sources")
                    browser.close()
                    return [] # Graceful degradation

            projects = []
            seen_urls = set()
            max_projects = MAX_PROJECTS

            for idx, link in enumerate(project_links):
                if len(projects) >= max_projects:
                    print(f"  Collected {max_projects} projects, stopping collection")
                    break

                try:
                    href = link.get_attribute("href")
                    text = link.inner_text()

                    if not href or not text.strip():
                        continue

                    if not href.startswith("http"):
                        href = "https://cryptorank.io" + href

                    # Fix: Convert /ico/ URLs to /price/ URLs for proper project page access
                    if '/ico/' in href:
                        href = href.replace('/ico/', '/price/')
                        print(f" Converted ICO URL to price URL: {href}")

                    if href in seen_urls:
                        continue

                    seen_urls.add(href)
                    projects.append({
                        "name": text.strip(),
                        "url": href,
                        "source": "cryptorank_funding_rounds",
                        "source_url": "https://cryptorank.io/funding-rounds",
                        "source_type": "funding_platform"
                    })

                except Exception as e:
                    print(f"  Error processing link {idx}: {str(e)}")
                    continue

            browser.close()

            print(f"\n{'='*60}")
            print(f" Total unique projects found: {len(projects)}")
            print(f"{'='*60}\n")

            return projects

    except Exception as e:
        print(f" CryptoRank scraping failed: {str(e)}")
        print(" ℹ Continuing with other data sources...")
        return [] # Graceful degradation - return empty list instead of crashing

def get_projects_from_rootdata():
    """Fetch projects from RootData fundraising page"""
    url = "https://www.rootdata.com/Fundraising"
    print(f"\n{'='*60}")
    print(f" SOURCE 2: Fetching projects from RootData")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Set longer timeout for page navigation
        page.set_default_timeout(60000) # 60 seconds
        
        print(" Loading page...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use 'load' instead of 'networkidle' for more reliable loading
                page.goto(url, wait_until="load", timeout=60000)
                print(" Page loaded successfully")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f" Attempt {attempt + 1} failed: {str(e)}")
                    print(f" Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f" All {max_retries} attempts failed. Trying with 'domcontentloaded' as fallback...")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        print(" Page loaded with fallback method")
                        break
                    except Exception as e2:
                        print(f" Fallback also failed: {str(e2)}")
                        browser.close()
                        raise Exception(f"Failed to load RootData page after {max_retries} attempts: {str(e2)}")
        
        time.sleep(5)
        print(" Waited 5 seconds for JavaScript to render")
        
        print("\n Searching for project links...")
        # Only select links in the sticky first column (Project column), not Investors column
        # The Project column uses td.b-table-sticky-column, while Investors use td.align_left
        project_links = page.locator("td.b-table-sticky-column a[href*='/Projects/detail/']").all()
        print(f" Found {len(project_links)} potential project links")
        
        projects = []
        seen_names = set()
        max_projects = MAX_PROJECTS
        
        for idx, link in enumerate(project_links):
            if len(projects) >= max_projects:
                print(f"  Collected {max_projects} projects, stopping collection")
                break
            
            try:
                href = link.get_attribute("href")
                text = link.inner_text()
                
                if not href or not text.strip():
                    continue
                
                if not href.startswith("http"):
                    href = "https://www.rootdata.com" + href

                # Extract clean name from URL path (more reliable than inner_text which
                # can include ticker badges like "MYX FinanceMYX" instead of "MYX Finance")
                from urllib.parse import unquote
                url_name = href.split('/Projects/detail/')[-1].split('?')[0]
                url_name = unquote(url_name).strip()

                clean_name = url_name if url_name else text.strip().split('\n')[0]
                if clean_name in seen_names or len(clean_name) < 2:
                    continue
                
                seen_names.add(clean_name)
                projects.append({
                    "name": clean_name,
                    "url": href,
                    "source": "rootdata_fundraising",
                    "source_url": "https://www.rootdata.com/Fundraising",
                    "source_type": "funding_platform"
                })
                
            except Exception as e:
                print(f"  Error processing link {idx}: {str(e)}")
                continue
        
        browser.close()
        
        print(f"\n{'='*60}")
        print(f" Total RootData projects found: {len(projects)}")
        print(f"{'='*60}\n")
        
        return projects

def get_all_projects():
    """Fetch and merge projects from all sources"""
    cryptorank_projects = get_projects_from_cryptorank()
    rootdata_projects = get_projects_from_rootdata()
    
    # Merge projects, avoiding duplicates by name (case-insensitive)
    all_projects = []
    seen_names = set()
    
    for project in cryptorank_projects + rootdata_projects:
        clean_name = re.sub(r'\n.*', '', project['name']).strip()
        clean_name = re.sub(r'\$.*', '', clean_name).strip()
        name_key = clean_name.lower()

        if len(clean_name) <= 1:
            continue

        # Check for exact match or prefix/substring overlap (handles "LayerZero" vs "LayerZeroZRO")
        is_duplicate = False
        for seen in seen_names:
            if name_key == seen or name_key.startswith(seen) or seen.startswith(name_key):
                is_duplicate = True
                break

        if not is_duplicate:
            seen_names.add(name_key)
            all_projects.append({
                "name": clean_name,
                "url": project['url'],
                "source": project.get('source', 'cryptorank_funding_rounds'),
                "source_url": project.get('source_url', 'https://cryptorank.io/funding-rounds'),
                "source_type": project.get('source_type', 'funding_platform')
            })
    
    print(f"\n{'='*60}")
    print(f" MERGED PROJECTS FROM ALL SOURCES")
    print(f" CryptoRank: {len(cryptorank_projects)} projects")
    print(f" RootData: {len(rootdata_projects)} projects")
    print(f" Total unique: {len(all_projects)} projects")
    print(f"{'='*60}\n")
    
    return all_projects

def extract_company_website(project_url):
    """Extract company website from main project page (not ICO/team pages)"""
    print(f"\n Extracting company website from main project page: {project_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Set longer timeout for page navigation
        page.set_default_timeout(60000) # 60 seconds
        
        try:
            # Use 'load' instead of 'networkidle' for more reliable loading
            page.goto(project_url, wait_until="load", timeout=60000)
            print(" Main project page loaded")
            
            time.sleep(3) # Give more time for dynamic content
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            website = None
            
            # For CryptoRank: Look for website link in the Links section
            if 'cryptorank.io' in project_url:
                print(" Looking for website in CryptoRank Links section...")
                
                # Look for the "Links" section with multiple approaches
                links_section = None
                
                # First, try to find the exact "Links" text (not containing "Links")
                links_text = soup.find(text=lambda text: text and text.strip() == 'Links')
                if links_text:
                    links_section = links_text.parent
                    print(f" Found exact 'Links' text in {links_section.name}")
                else:
                    # Fallback to other methods
                    links_section = soup.find('div', string=re.compile(r'Links', re.I))
                    if not links_section:
                        links_section = soup.find('h3', string=re.compile(r'Links', re.I))
                    if not links_section:
                        links_section = soup.find('span', string=re.compile(r'Links', re.I))
                    if not links_section:
                        # Look for any element containing "Links"
                        links_section = soup.find(text=re.compile(r'Links', re.I))
                        if links_section:
                            links_section = links_section.parent
                
                if links_section:
                    print(" Found 'Links' section")
                    # Find the parent container of the Links section
                    links_container = links_section.find_parent()
                    if links_container:
                        # Look for the "Website" button specifically with more comprehensive search
                        website_buttons = links_container.find_all('a', href=True)
                        print(f" Found {len(website_buttons)} links in Links section")
                        
                        for link in website_buttons:
                            href = link.get('href', '')
                            text = link.get_text(strip=True).lower()
                            
                            print(f" Checking link: '{text}' -> {href}")
                            
                            # Look specifically for the "Website" button - improved matching
                            if ('website' in text or 'site' in text) and href.startswith('http'):
                                # Additional validation to ensure it's not a social media link
                                if not any(social in href.lower() for social in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'breakingthenews.net']):
                                    website = href
                                    print(f" Found Website button: {href}")
                                    break
                
                # If no website found in Links section, look for sibling elements
                if not website and links_section:
                    print(" No website in Links section, checking sibling elements...")
                    links_parent = links_section.find_parent()
                    if links_parent:
                        # Look for sibling divs that might contain the links
                        siblings = links_parent.find_next_siblings()
                        for sibling in siblings:
                            if sibling.name == 'div':
                                sibling_links = sibling.find_all('a', href=True)
                                print(f" Found {len(sibling_links)} links in sibling div")
                                
                                for link in sibling_links:
                                    href = link.get('href', '')
                                    text = link.get_text(strip=True).lower()
                                    
                                    print(f" Checking sibling link: '{text}' -> {href}")
                                    
                                    # Look for website links
                                    if ('website' in text or 'site' in text) and href.startswith('http'):
                                        if not any(social in href.lower() for social in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'breakingthenews.net']):
                                            website = href
                                            print(f" Found Website in sibling: {href}")
                                            break
                                if website:
                                    break
                
                # If still no website found, try looking for the Links section more broadly
                if not website:
                    print(" Trying broader search for Links section...")
                    # Look for any section that might contain links
                    potential_sections = soup.find_all(['div', 'section'], class_=lambda x: x and any(keyword in x.lower() for keyword in ['link', 'social', 'connect']))
                    
                    for section in potential_sections:
                        links_in_section = section.find_all('a', href=True)
                        for link in links_in_section:
                            href = link.get('href', '')
                            text = link.get_text(strip=True).lower()
                            
                            # Look for website indicators
                            if ('website' in text or 'site' in text) and href.startswith('http'):
                                if not any(social in href.lower() for social in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'breakingthenews.net']):
                                    website = href
                                    print(f" Found Website in broader search: {href}")
                                    break
                        if website:
                            break
                
                # If no Website button found in Links section, try broader search
                if not website:
                    print(" No Website button found, trying broader search...")
                    all_links = soup.find_all('a', href=True)
                    print(f" Found {len(all_links)} total links on page")
                    
                    # First, try to find links that look like company websites
                    potential_websites = []
                    for link in all_links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        
                        # Skip social media and internal links
                        if any(skip in href.lower() for skip in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'cryptorank.io', 'bcgame.bet', 'breakingthenews.net']):
                            continue
                        
                        # Look for main website indicators
                        if href.startswith('http'):
                            domain = urlparse(href).netloc.lower()
                            # Check if it looks like a company website (simple domain names)
                            if '.' in domain and not any(skip in domain for skip in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'notion.so', 'calendly.com', 'drive.google.com', 'apps.apple.com']):
                                potential_websites.append((href, text, domain))
                    
                    # Sort by domain length (shorter domains are more likely to be company websites)
                    potential_websites.sort(key=lambda x: len(x[2]))
                    
                    if potential_websites:
                        website = potential_websites[0][0]
                        print(f" Found potential website: {website}")
                    else:
                        print("  No suitable website found")
            
            # For RootData: Look for website link in project details
            elif 'rootdata.com' in project_url:
                print(" Looking for website in RootData project details...")
                
                # Use longer timeout for RootData pages
                try:
                    page.goto(project_url, wait_until="load", timeout=60000)
                    time.sleep(3)
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    print(" RootData page loaded successfully")
                except:
                    print("  RootData page load failed, using existing content")
                
                # Look for website links in the main content area
                website_links = soup.find_all('a', href=True)
                print(f" Found {len(website_links)} links on RootData page")
                
                # Look for the specific website link pattern (like tempo.xyz)
                # This should be in the main content area below the project description
                for link in website_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Skip social media and internal links
                    if any(skip in href.lower() for skip in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'rootdata.com']):
                        continue
                    
                    # Look for main website indicators
                    if href.startswith('http'):
                        # Check if this looks like a company website (not social media or services)
                        domain = urlparse(href).netloc.lower()
                        if not any(skip in domain for skip in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'notion.so', 'calendly.com', 'drive.google.com', 'apps.apple.com']):
                            website = href
                            print(f" Found company website link: {href}")
                            break
            
            browser.close()
            
            if website:
                # Filter out telegram URLs - they're not valid company websites
                if 't.me' in website.lower() or 'telegram' in website.lower():
                    print(f" Found telegram URL instead of website: {website}")
                    print(" Skipping - telegram URLs are not valid for Apollo enrichment")
                    return None
                
                # Clean up the website URL
                if not website.startswith('http'):
                    website = 'https://' + website
                
                # Extract domain for Apollo search
                try:
                    domain = urlparse(website).netloc
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    
                    # Double-check domain is not telegram
                    if 't.me' in domain.lower() or 'telegram' in domain.lower():
                        print(f" Domain appears to be telegram: {domain}")
                        print(" Skipping - telegram domains are not valid for Apollo enrichment")
                        return None
                    
                    print(f" Successfully found website: {website} (domain: {domain})")
                    return {"website": website, "domain": domain}
                except:
                    print(f" Could not parse website URL: {website}")
                    return None
            else:
                print(" No company website found on main project page")
                return None
                
        except Exception as e:
            print(f" Error extracting website: {str(e)}")
            browser.close()
            return None

def fetch_team_from_apollo(company_name, company_website=None):
    """Apollo.io API fallback for team members

    Uses a two-step workflow:
    1. Search with mixed_people/api_search to get person IDs (returns obfuscated data)
    2. Enrich with people/bulk_match using IDs to get full profiles (names, LinkedIn, etc.)
    """
    print(f"\n{'='*60}")
    print(f" APOLLO: Searching for {company_name} team on Apollo.io")
    print(f"{'='*60}")

    clean_name = re.sub(r'\$.*', '', company_name).strip()
    clean_name = re.sub(r'\n.*', '', clean_name).strip()
    print(f" Cleaned company name: '{clean_name}'")

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY
    }

    # Target executive/leadership titles
    target_titles = [
        "CEO", "CFO", "COO", "Chief Executive", "Chief Financial", "Chief Operating",
        "Co-Founder", "Founder", "Co Founder", "Cofounder",
        "VP", "Vice President", "V.P.",
        "Director", "Managing Director",
        "General Manager", "Growth", "Head of",
        "Chief of Staff", "President"
    ]

    # Target seniority levels for better filtering
    target_seniorities = ["c_suite", "founder", "owner", "vp", "director", "head"]

    # STEP 1: Search for people (returns obfuscated data with IDs)
    # Use correct Apollo API parameter names (q_organization_domains_list as array)
    if company_website and company_website.get('domain'):
        domain = company_website['domain']
        print(f" Using website domain for search: '{domain}'")
        payload = {
            "q_organization_domains_list": [domain], # Must be array with _list suffix
            "person_titles": target_titles,
            "person_seniorities": target_seniorities,
            "page": 1,
            "per_page": 25
        }
    else:
        print(f" Using company name for search: '{clean_name}'")
        payload = {
            "q_organization_name": clean_name,
            "person_titles": target_titles,
            "person_seniorities": target_seniorities,
            "page": 1,
            "per_page": 25
        }

    members = []

    try:
        # Step 1: Search to get person IDs
        print(f" Step 1: Searching Apollo database...")
        response = requests.post(APOLLO_API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            people = data.get('people', [])

            print(f" Apollo search found {len(people)} potential team members")

            if not people:
                print(f" ℹ No people found matching criteria")
                return members

            # Filter out non-target roles - collect IDs for enrichment
            person_ids = []
            excluded_roles = {
                # CTO/Tech/Engineering roles
                'cto', 'chief technology', 'tech lead', 'engineer', 'engineering',
                'developer', 'software', 'backend', 'frontend', 'full stack', 'fullstack',
                'devops', 'sre', 'infrastructure', 'architect', 'technical', 'security', 'privacy',
                # HR roles
                'hr', 'human resource', 'people operations', 'people ops', 'talent',
                'recruiting', 'recruiter', 'recruitment', 'hiring',
                # Trading roles
                'trader', 'trading', 'quant', 'quantitative', 'portfolio manager',
                'market maker', 'market making', 'derivatives', 'prop trading',
                # Sales roles
                'sales', 'account executive', 'account manager', 'business development',
                'bdr', 'sdr', 'revenue', 'partnerships', 'partner manager',
                # Product roles
                'product', 'product manager', 'product owner', 'product lead', 'cpo',
                'chief product', 'product director', 'product head'
            }
            for person in people:
                title = person.get('title', '')
                title_lower = title.lower() if title else ''

                # Skip if title matches any excluded role
                if title_lower and any(excluded in title_lower for excluded in excluded_roles):
                    continue
                # Also skip CTO variations
                if title_lower and ('cto' in title_lower or 'chief technology' in title_lower or
                            ('tech' in title_lower and 'chief' in title_lower)):
                    continue
                person_id = person.get('id')
                if person_id:
                    person_ids.append(person_id)

            if not person_ids:
                print(f" ℹ No eligible people after filtering CTOs")
                return members

            print(f" {len(person_ids)} people eligible for enrichment (after excluding CTOs)")

            # Step 2: Enrich in batches of 10 (Apollo limit)
            print(f" Step 2: Enriching profiles to get full data...")
            enriched_count = 0

            for i in range(0, len(person_ids), 10):
                batch_ids = person_ids[i:i+10]
                details = [{"id": pid} for pid in batch_ids]

                enrich_payload = {"details": details}

                try:
                    enrich_response = requests.post(
                        APOLLO_BULK_ENRICHMENT_URL,
                        headers=headers,
                        json=enrich_payload,
                        timeout=30
                    )

                    if enrich_response.status_code == 200:
                        enrich_data = enrich_response.json()
                        matches = enrich_data.get('matches', [])

                        for person in matches:
                            # Get full name from enriched data
                            name = person.get('name')
                            if not name:
                                first_name = person.get('first_name', '')
                                last_name = person.get('last_name', '')
                                name = f"{first_name} {last_name}".strip()

                            if not name:
                                continue

                            title = person.get('title')
                            title = title.strip() if title else None
                            title_lower = title.lower() if title else ''

                            # Skip CTOs, HR, and trading roles that might have slipped through
                            if title_lower and any(excluded in title_lower for excluded in excluded_roles):
                                continue
                            if title_lower and ('cto' in title_lower or 'chief technology' in title_lower):
                                continue

                            linkedin_url = person.get('linkedin_url')
                            if linkedin_url and linkedin_url.startswith('http://'):
                                linkedin_url = linkedin_url.replace('http://', 'https://')

                            twitter_url = person.get('twitter_url')

                            apollo_person_id = person.get('id')
                            email = person.get('email')

                            member_data = {
                                "name": name,
                                "role": title,
                                "linkedin_url": linkedin_url,
                                "twitter_url": twitter_url,
                                "email": email,
                                "apollo_person_id": apollo_person_id,
                                "source": "apollo_api",
                                "source_url": APOLLO_API_URL
                            }
                            members.append(member_data)
                            enriched_count += 1

                            linkedin_str = "with LinkedIn" if linkedin_url else "no LinkedIn"
                            twitter_str = f", Twitter: {twitter_url}" if twitter_url else ""
                            email_str = f", email: {email}" if email else ""
                            print(f" {enriched_count}. {name} - {title if title else 'No role'}, {linkedin_str}{twitter_str}{email_str}")

                    elif enrich_response.status_code == 429:
                        print(f"  Rate limit reached during enrichment, returning partial results")
                        break
                    else:
                        print(f"  Enrichment batch failed with status {enrich_response.status_code}")

                except requests.exceptions.Timeout:
                    print(f"  Enrichment request timed out")
                except Exception as e:
                    print(f"  Enrichment error: {str(e)}")

            print(f"\n Apollo returned {len(members)} enriched team members")

        elif response.status_code == 429:
            print(f"  Rate limit reached on Apollo API")
        elif response.status_code == 401:
            print(f" Apollo API authentication failed - check API key")
        else:
            print(f"  Apollo API returned status {response.status_code}")
            try:
                print(f" Response: {response.text[:300]}")
            except:
                pass

    except requests.exceptions.Timeout:
        print(f"  Apollo API request timed out")
    except Exception as e:
        print(f" Error with Apollo API: {str(e)}")

    return members

def enrich_people_with_emails(people_with_linkedin):
    """Enrich people with emails using Apollo bulk enrichment API
    
    Uses Apollo person ID when available (for Apollo-sourced data) for better matches.
    Falls back to LinkedIn URL for scraped data.
    Filters out telegram URLs to avoid wasting API resources.
    """
    if not people_with_linkedin:
        return {}
    
    print(f"\n{'='*60}")
    print(f" APOLLO BULK ENRICHMENT: Enriching {len(people_with_linkedin)} people with emails")
    print(f"{'='*60}")
    
    # Apollo bulk enrichment supports up to 10 people per request
    batch_size = 10
    enrichment_results = {}
    
    # Filter out people with invalid URLs (telegram, etc.) before processing
    valid_people = []
    skipped_count = 0
    
    for person in people_with_linkedin:
        linkedin_url = person.get('linkedin_url')
        apollo_person_id = person.get('apollo_person_id')
        
        # Skip if no identifier available
        if not linkedin_url and not apollo_person_id:
            skipped_count += 1
            continue
        
        # Filter out telegram URLs - they're not valid for enrichment
        if linkedin_url and ('t.me' in linkedin_url.lower() or 'telegram' in linkedin_url.lower()):
            print(f"  Skipping {person.get('name', 'Unknown')}: Invalid URL (telegram link)")
            skipped_count += 1
            continue
        
        valid_people.append(person)
    
    if skipped_count > 0:
        print(f" ℹ Filtered out {skipped_count} invalid entries")
    
    if not valid_people:
        print(f"  No valid people to enrich after filtering")
        return {}
    
    print(f" Processing {len(valid_people)} valid people for enrichment")
    
    for i in range(0, len(valid_people), batch_size):
        batch = valid_people[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(valid_people) + batch_size - 1) // batch_size
        
        print(f"\n Processing batch {batch_num}/{total_batches} ({len(batch)} people)...")
        
        # Prepare details array for Apollo API
        details = []
        batch_mapping = [] # Store person info for result mapping
        
        for person in batch:
            apollo_person_id = person.get('apollo_person_id')
            linkedin_url = person.get('linkedin_url')
            
            detail = {}
            
            # Prefer Apollo person ID for better matches (when available)
            if apollo_person_id:
                detail["id"] = apollo_person_id # Apollo API uses 'id' not 'person_id'
                print(f" Using Apollo person ID for {person.get('name', 'Unknown')}")
            elif linkedin_url:
                # Fallback to LinkedIn URL for scraped data
                detail["linkedin_url"] = linkedin_url
                
                # Extract name parts if available for better matching
                name = person.get('name', '')
                name_parts = name.split() if name else []
                first_name = name_parts[0] if len(name_parts) > 0 else None
                last_name = name_parts[-1] if len(name_parts) > 1 else None
                
                if first_name:
                    detail["first_name"] = first_name
                if last_name and last_name != first_name:
                    detail["last_name"] = last_name
                
                print(f" Using LinkedIn URL for {person.get('name', 'Unknown')}")
            else:
                # Skip if no identifier
                continue
            
            details.append(detail)
            batch_mapping.append(person)
        
        if not details:
            print(f"  No valid identifiers in batch, skipping...")
            continue
        
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": APOLLO_API_KEY
        }

        payload = {
            "details": details,
            "reveal_personal_emails": True
        }
        
        try:
            response = requests.post(APOLLO_BULK_ENRICHMENT_URL, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Apollo API can return matches in different formats
                # Try 'matches' array first, then 'people' array, then direct array
                matches = data.get('matches', [])
                if not matches:
                    matches = data.get('people', [])
                if not matches and isinstance(data, list):
                    matches = data
                
                print(f" Apollo returned {len(matches)} enriched matches")
                
                # Process matches and map back to original people
                # Match order should correspond to details array order
                for match_idx, match in enumerate(matches):
                    if match_idx < len(batch_mapping):
                        person = batch_mapping[match_idx]
                        
                        # Extract email from match - handle different response structures
                        email = None
                        
                        # Try different email field structures
                        if isinstance(match, dict):
                            # Direct email field
                            email = match.get('email')
                            
                            # Emails array structure
                            if not email:
                                emails = match.get('emails', [])
                                if emails:
                                    # Handle array of email strings
                                    if isinstance(emails[0], str):
                                        email = emails[0]
                                    # Handle array of email objects
                                    elif isinstance(emails[0], dict):
                                        # Prefer personal email if available
                                        for email_obj in emails:
                                            if email_obj.get('type') == 'personal' or not email_obj.get('type'):
                                                email = email_obj.get('email') or email_obj.get('address')
                                                break
                                        # Fallback to first email if no personal email found
                                        if not email and emails:
                                            email = emails[0].get('email') or emails[0].get('address')
                            
                            # Try personal_email field
                            if not email:
                                email = match.get('personal_email')
                            
                            # Try work_email field
                            if not email:
                                email = match.get('work_email')
                        
                        # Store enrichment result using person ID or LinkedIn URL as key
                        apollo_person_id = person.get('apollo_person_id')
                        linkedin_url = person.get('linkedin_url')
                        
                        # Use person ID as primary key if available, otherwise LinkedIn URL
                        result_key = apollo_person_id if apollo_person_id else linkedin_url
                        
                        if result_key:
                            enrichment_results[result_key] = {
                                'email': email,
                                'person_name': person.get('name'),
                                'key_type': 'person_id' if apollo_person_id else 'linkedin_url'
                            }
                            
                            if email:
                                method_str = "person ID" if apollo_person_id else "LinkedIn URL"
                                print(f" {person.get('name', 'Unknown')} ({method_str}): {email}")
                            else:
                                print(f"  {person.get('name', 'Unknown')}: No email found")
                
            elif response.status_code == 429:
                print(f"  Rate limit reached on Apollo API, waiting 60 seconds...")
                time.sleep(60)
            elif response.status_code == 401:
                print(f" Apollo API authentication failed - check API key")
                break
            else:
                print(f"  Apollo API returned status {response.status_code}: {response.text[:200]}")
            
            # Add delay between batches to respect rate limits
            if i + batch_size < len(people_with_linkedin):
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            print(f"  Apollo API request timed out")
        except Exception as e:
            print(f" Error with Apollo bulk enrichment API: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n Bulk enrichment complete: {len(enrichment_results)} people enriched with emails")
    return enrichment_results

def fetch_team_members(project_url):
    print(f"\n{'='*60}")
    print(f" STEP 2: Fetching team members from {project_url}")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Convert /ico/ URLs to /price/.../team format
        team_url = project_url.replace('/ico/', '/price/') 
        if not team_url.endswith('/team'):
            team_url = team_url.split('#')[0]
            team_url = team_url.rstrip('/') + '/team'
        
        # Set longer timeout for page navigation
        page.set_default_timeout(60000) # 60 seconds
        
        print(f" Loading team page: {team_url}")
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Use 'load' instead of 'networkidle' for more reliable loading
                page.goto(team_url, wait_until="load", timeout=60000)
                print(" Team page loaded")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f" Attempt {attempt + 1} failed: {str(e)}")
                    print(f" Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print(f" Error loading team page after {max_retries} attempts: {str(e)}")
                    # Try fallback with domcontentloaded
                    try:
                        page.goto(team_url, wait_until="domcontentloaded", timeout=60000)
                        print(" Team page loaded with fallback method")
                        break
                    except Exception as e2:
                        print(f" Fallback also failed: {str(e2)}")
                        browser.close()
                        return []
        
        time.sleep(3)
        print(" Waited 3 seconds for JavaScript to render")
        
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        print("\n Searching for team members...")
        members = []
        
        try:
            name_pattern = re.compile(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,3}$')

            # Find name tags using CSS module class prefix (stable across deployments)
            name_tags = soup.find_all('p', class_=lambda x: x and any('styles_name__' in c for c in (x if isinstance(x, list) else [x])))
            print(f" Found {len(name_tags)} team member elements")

            excluded_keywords = [
                'cto', 'chief technology', 'tech lead', 'engineer', 'engineering',
                'developer', 'software', 'backend', 'frontend', 'full stack', 'fullstack',
                'devops', 'sre', 'infrastructure', 'architect', 'technical',
                'hr', 'human resource', 'people operations', 'people ops', 'talent',
                'recruiting', 'recruiter', 'recruitment', 'hiring',
                'trader', 'trading', 'quant', 'quantitative', 'portfolio manager',
                'market maker', 'market making', 'derivatives', 'prop trading',
                'sales', 'account executive', 'account manager', 'business development',
                'bdr', 'sdr', 'revenue', 'partnerships', 'partner manager',
                'product', 'product manager', 'product owner', 'product lead', 'cpo',
                'chief product', 'product director', 'product head'
            ]

            for name_tag in name_tags:
                name = name_tag.get_text(strip=True)

                if not name_pattern.match(name):
                    continue

                role = None
                linkedin_url = None
                twitter_url = None

                # Find the card container (parent div with styles_container__ class)
                card = name_tag.find_parent('div', class_=lambda x: x and any('styles_container__' in c for c in (x if isinstance(x, list) else [x])))
                if not card:
                    # Fallback: walk up to great-grandparent
                    card = name_tag.find_parent()
                    if card:
                        card = card.find_parent()
                    if card:
                        card = card.find_parent()

                if card:
                    # Extract role from badge button or span
                    badge = card.find('button', class_=lambda x: x and any('styles_badge_root__' in c for c in (x if isinstance(x, list) else [x])))
                    if badge:
                        role = badge.get_text(strip=True)
                    else:
                        # Fallback: look for next sibling <p> (old layout)
                        next_p = name_tag.find_next_sibling('p')
                        if next_p:
                            potential_role = next_p.get_text(strip=True)
                            if potential_role and len(potential_role) < 50 and not name_pattern.match(potential_role):
                                role = potential_role

                    # Extract social links from the card container
                    for a in card.find_all('a', href=True):
                        href = a['href']
                        if not linkedin_url and 'linkedin.com' in href.lower():
                            linkedin_url = href
                        elif not twitter_url and ('twitter.com' in href.lower() or 'x.com' in href.lower()):
                            twitter_url = href

                if role and any(kw in role.lower() for kw in excluded_keywords):
                    continue

                member_data = {
                    "name": name,
                    "role": role,
                    "linkedin_url": linkedin_url,
                    "twitter_url": twitter_url,
                    "source": "cryptorank_team_page",
                    "source_url": team_url
                }
                members.append(member_data)

                linkedin_str = "with LinkedIn" if linkedin_url else "no LinkedIn"
                twitter_str = "with Twitter" if twitter_url else "no Twitter"
                print(f" {len(members)}. {name} - {role if role else 'No role found'}, {linkedin_str}, {twitter_str}")
        
        except Exception as e:
            print(f" Error parsing team members: {str(e)}")
            import traceback
            traceback.print_exc()
        
        browser.close()
        
        print(f"\n Total team members found: {len(members)}")
        return members

def extract_twitter_username(twitter_url):
    """Extract username from a Twitter/X URL"""
    if not twitter_url:
        return None
    url = twitter_url.strip().rstrip('/')
    # Handle twitter.com/username and x.com/username
    match = re.search(r'(?:twitter\.com|x\.com)/(@?[\w]+)', url, re.IGNORECASE)
    if match:
        username = match.group(1).lstrip('@')
        # Skip non-profile paths
        if username.lower() in ('home', 'explore', 'search', 'settings', 'i', 'intent', 'share'):
            return None
        return username
    return None

def get_company_shorthands(company_name):
    """Derive shorthand tokens from a company name for username pattern generation.

    e.g. "Open Campus" → ["open", "campus", "opencampus", "oc"]
         "LayerZero Labs" → ["layer", "zero", "layerzero", "lz"]
         "DeFi Technologies" → ["defi"]
    """
    if not company_name or not company_name.isascii():
        return []

    SUFFIXES = {
        'labs', 'protocol', 'protocols', 'network', 'networks', 'finance',
        'technologies', 'technology', 'tech', 'dao', 'foundation', 'capital',
        'ventures', 'venture', 'inc', 'ltd', 'llc', 'co', 'corp', 'group',
        'platform', 'platforms', 'exchange', 'markets', 'market', 'ecosystem'
    }

    # Split camelCase boundaries first, then split on spaces/hyphens/underscores
    name_spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', company_name.strip())
    words = re.split(r'[\s\-_]+', name_spaced)
    words = [w for w in words if w]

    meaningful = [w for w in words if w.lower() not in SUFFIXES]
    if not meaningful:
        meaningful = words  # fallback: nothing was left after stripping suffixes

    shorthands = set()

    # Each meaningful word individually
    for w in meaningful:
        clean = re.sub(r'[^a-zA-Z0-9]', '', w)
        if clean and len(clean) >= 2:
            shorthands.add(clean.lower())

    # Full joined form (for multi-word companies)
    if len(meaningful) > 1:
        full = re.sub(r'[^a-zA-Z0-9]', '', ''.join(meaningful))
        if full:
            shorthands.add(full.lower())
        # Initials (e.g. "Open Campus" → "oc")
        if 2 <= len(meaningful) <= 4:
            initials = ''.join(w[0] for w in meaningful if w)
            if len(initials) >= 2:
                shorthands.add(initials.lower())

    return list(shorthands)


def score_entity_match(entity, person_name, candidate, candidate_idx, company_shorthands):
    """Score how well a Telegram entity matches a person.

    Returns a float score (higher = better match), or None if first name doesn't match
    (used to reject obvious false positives).

    Scoring:
      +3  first name AND last name both match TG profile
      +1  first name matches only (last name often missing on TG)
      +1  candidate contains a company shorthand (more specific pattern)
      +0–0.5  small positional bonus (earlier candidates are more likely)
    None → first name doesn't match at all → reject
    """
    tg_first = (entity.first_name or '').lower().strip()
    tg_last  = (entity.last_name  or '').lower().strip()
    parts = person_name.lower().split()
    person_first = parts[0] if parts else ''
    person_last  = parts[-1] if len(parts) > 1 else ''

    first_match = bool(person_first and (person_first in tg_first or tg_first in person_first))
    last_match  = bool(person_last  and (person_last  in tg_last  or tg_last  in person_last))

    if not first_match:
        return None  # Reject — first name is the minimum bar

    score = 3.0 if (first_match and last_match) else 1.0

    # Company-pattern bonus: candidate contains a company shorthand
    candidate_lower = candidate.lower()
    if any(co in candidate_lower for co in company_shorthands):
        score += 1.0

    # Small positional bonus: earlier candidates are more likely patterns
    score += max(0.0, 0.5 - candidate_idx * 0.02)

    return score


def generate_name_candidates(name, company_name=None):
    """Generate Telegram username candidates from a person's name and company.

    Candidate order (most → least likely):
      1. first_co, firstCo, co_first, CoFirst  (first + company)
      2. last_co,  lastCo,  co_last,  CoLast   (last  + company)
      3. no-separator variants: firstco, cofirst, lastco, colast
      4. JohnDoe, john_doe, johndoe             (name-only)
      5. johnd, jdoe                            (abbreviated)

    Returns deduplicated list of valid TG usernames (5–32 chars, [a-zA-Z0-9_]).
    """
    if not name:
        return []
    parts = name.strip().split()
    if len(parts) < 2:
        return []
    first = parts[0]
    last  = parts[-1]
    if not first.isascii() or not last.isascii():
        return []

    seen = set()
    candidates = []

    def add(raw_list):
        for c in raw_list:
            clean = re.sub(r'[^a-zA-Z0-9_]', '', c)
            if 5 <= len(clean) <= 32 and clean not in seen:
                seen.add(clean)
                candidates.append(clean)

    f  = first.lower()
    l  = last.lower()
    Fc = first[0].upper() + first[1:].lower()  # Title-cased first
    Lc = last[0].upper()  + last[1:].lower()   # Title-cased last

    # --- Company-inclusive patterns (highest priority) ---
    if company_name:
        for co in get_company_shorthands(company_name):
            Co = co[0].upper() + co[1:]  # Title-cased company shorthand
            add([
                # first + company
                f"{f}_{co}",        # john_aethir
                f"{f}{Co}",         # johnAethir
                f"{Co}_{Fc}",       # Aethir_John
                f"{co}_{f}",        # aethir_john
                f"{f}{co}",         # johnaethir
                f"{co}{f}",         # aethirjohn
                # last + company
                f"{l}_{co}",        # smith_aethir
                f"{l}{Co}",         # smithAethir
                f"{Co}_{Lc}",       # Aethir_Smith
                f"{co}_{l}",        # aethir_smith
                f"{l}{co}",         # smithaethir
                f"{co}{l}",         # aethirsmith
            ])

    # --- Name-only patterns (lower priority) ---
    add([
        f"{first}{last}",   # JohnDoe
        f"{f}{l}",          # johndoe
        f"{f}_{l}",         # john_doe
        f"{f}{l[0]}",       # johnd
        f"{f[0]}{l}",       # jdoe
    ])

    return candidates

def resolve_telegram_usernames(people):
    """Resolve Telegram usernames in two passes:

    Pass 1: Check Twitter handles on Telegram (existing behavior).
    Pass 2: For anyone still without a TG username, try common name-based
            patterns (FirstLast, first_last, etc.).
    """
    try:
        client = TelegramClient(StringSession(TELEGRAM_SESSION), TELEGRAM_API_ID, TELEGRAM_API_HASH)
        client.connect()

        if not client.is_user_authorized():
            print(" Telegram session is not authorized, skipping resolution")
            client.disconnect()
            return

        resolved_count = 0
        total_checked = 0

        # --- Pass 1: Twitter handles ---
        username_to_people = {}
        for person in people:
            username = extract_twitter_username(person.get('twitter_url'))
            if username:
                username_to_people.setdefault(username, []).append(person)

        if username_to_people:
            unique_usernames = list(username_to_people.keys())
            print(f" [Pass 1] Checking {len(unique_usernames)} Twitter usernames on Telegram...")

            for i, username in enumerate(unique_usernames):
                total_checked += 1
                try:
                    entity = client.get_entity(username)
                    if isinstance(entity, User):
                        resolved_count += 1
                        tg_username = f"@{entity.username}" if entity.username else f"@{username}"
                        for person in username_to_people[username]:
                            person['telegram_username'] = tg_username
                        print(f" {username} Telegram user found: {tg_username}")
                    else:
                        print(f"  {username} not a user (channel/group)")
                except Exception:
                    print(f" {username} not found on Telegram")

                time.sleep(1.5)
        else:
            print(" [Pass 1] No Twitter usernames to check")

        # --- Pass 2: Name + company pattern matching for unresolved people ---
        unresolved = [p for p in people if not p.get('telegram_username') and p.get('name')]
        if unresolved:
            print(f"\n [Pass 2] Trying name/company patterns for {len(unresolved)} unresolved people...")

            name_resolved = 0
            for person in unresolved:
                person_name    = person['name']
                company_name   = person.get('project')
                co_shorthands  = get_company_shorthands(company_name) if company_name else []
                candidates     = generate_name_candidates(person_name, company_name)

                if not candidates:
                    continue

                found_matches = []  # (score, candidate, entity, tg_username)

                for idx, candidate in enumerate(candidates):
                    total_checked += 1
                    try:
                        entity = client.get_entity(candidate)
                        if isinstance(entity, User):
                            score = score_entity_match(
                                entity, person_name, candidate, idx, co_shorthands
                            )
                            if score is not None:
                                tg_username = f"@{entity.username}" if entity.username else f"@{candidate}"
                                found_matches.append((score, candidate, entity, tg_username))
                                # High-confidence hit (first+last match) — no need to keep looking
                                if score >= 3.0:
                                    break
                            else:
                                print(f"  {person_name}: {candidate} exists but name mismatch "
                                      f"(TG: {entity.first_name} {entity.last_name})")
                    except FloodWaitError as e:
                        print(f"  Rate limited — waiting {e.seconds}s before continuing...")
                        time.sleep(e.seconds + 2)
                        # Retry the same candidate once after the wait
                        try:
                            entity = client.get_entity(candidate)
                            if isinstance(entity, User):
                                score = score_entity_match(
                                    entity, person_name, candidate, idx, co_shorthands
                                )
                                if score is not None:
                                    tg_username = f"@{entity.username}" if entity.username else f"@{candidate}"
                                    found_matches.append((score, candidate, entity, tg_username))
                                    if score >= 3.0:
                                        break
                        except Exception:
                            pass
                    except Exception:
                        pass  # Username not found — silently skip

                    time.sleep(1.5)

                if found_matches:
                    # Rank by score descending; deduplicate by entity id
                    seen_ids = set()
                    unique_matches = []
                    for match in sorted(found_matches, key=lambda x: x[0], reverse=True):
                        eid = match[2].id
                        if eid not in seen_ids:
                            seen_ids.add(eid)
                            unique_matches.append(match)

                    best_score, best_candidate, _, best_tg = unique_matches[0]
                    person['telegram_username'] = best_tg
                    resolved_count += 1
                    name_resolved += 1

                    if len(unique_matches) > 1:
                        alts = ', '.join(
                            f"{tg} via {c} (score={s:.1f})"
                            for s, c, _, tg in unique_matches[1:]
                        )
                        person['telegram_alternatives'] = alts
                        print(f"  {person_name}: {best_tg} (score={best_score:.1f}, "
                              f"pattern={best_candidate}) | alternatives: {alts}")
                    else:
                        print(f"  {person_name}: {best_tg} "
                              f"(score={best_score:.1f}, pattern={best_candidate})")
                else:
                    print(f"  {person_name}: no match from {len(candidates)} candidates")

            print(f"\n [Pass 2] Name/company resolution: {name_resolved}/{len(unresolved)} resolved")

        client.disconnect()
    except Exception as e:
        print(f" Telegram connection error: {str(e)}")

    print(f"\n Telegram resolution complete: {resolved_count} total resolved, {total_checked} lookups")

def gather_all():
    """Main function to gather all team members from all sources"""
    print("\n" + "="*60)
    print(" STARTING DATA COLLECTION PROCESS")
    print("="*60)
    
    projects = get_all_projects()
    
    if not projects:
        print("\n ERROR: No projects found! Cannot continue.")
        return []
    
    all_people = []
    print(f"\n Processing all {len(projects)} projects\n")

    for idx, project in enumerate(projects, 1):
        print(f"\n{'='*60}")
        print(f" Processing {idx}/{len(projects)}: {project['name']}")
        print(f" Source: {project['source']}")
        print(f"{'='*60}")
        
        team = []

        # Extract company website first
        website_info = extract_company_website(project['url'])
        if website_info and website_info.get('domain'):
            print(f" Website found: {website_info['website']} (domain: {website_info['domain']})")
        else:
            print("  No website found")

        # Always scrape CryptoRank team page for CryptoRank projects
        if project['source'] == 'cryptorank_funding_rounds':
            team = fetch_team_members(project['url'])
        else:
            print(" ℹ RootData project - skipping team page, will use Apollo")

        # Use Apollo to supplement: fill missing LinkedIn/Twitter, add extra members
        should_use_apollo = False
        if not team:
            print("  No team members found - will try Apollo")
            should_use_apollo = True
        else:
            members_without_linkedin = [m for m in team if not m.get('linkedin_url')]
            if members_without_linkedin:
                print(f"  {len(members_without_linkedin)} team member(s) have no LinkedIn - will try Apollo")
                should_use_apollo = True
            elif website_info and website_info.get('domain'):
                print(f" ℹ Will also check Apollo for additional team members")
                should_use_apollo = True
        
        # Apollo search
        if should_use_apollo:
            time.sleep(2)
            apollo_team = fetch_team_from_apollo(project['name'], website_info)
            
            if apollo_team:
                existing_names = {m['name'].lower() for m in team}
                
                # Roles to exclude from results
                excluded_role_keywords = [
                    'cto', 'chief technology', 'tech lead', 'engineer', 'engineering',
                    'developer', 'software', 'backend', 'frontend', 'full stack', 'fullstack',
                    'devops', 'sre', 'infrastructure', 'architect', 'technical',
                    'hr', 'human resource', 'people operations', 'people ops', 'talent',
                    'recruiting', 'recruiter', 'recruitment', 'hiring',
                    'trader', 'trading', 'quant', 'quantitative', 'portfolio manager',
                    'market maker', 'market making', 'derivatives', 'prop trading',
                    'sales', 'account executive', 'account manager', 'business development',
                    'bdr', 'sdr', 'revenue', 'partnerships', 'partner manager',
                    'product', 'product manager', 'product owner', 'product lead', 'cpo',
                    'chief product', 'product director', 'product head'
                ]
                for apollo_member in apollo_team:
                    apollo_role = apollo_member.get('role', '')
                    role_lower = apollo_role.lower() if apollo_role else ''
                    if role_lower and any(excluded in role_lower for excluded in excluded_role_keywords):
                        continue
                    
                    if apollo_member['name'].lower() not in existing_names:
                        team.append(apollo_member)
                        print(f" Added from Apollo: {apollo_member['name']}")
                    else:
                        for existing_member in team:
                            if existing_member['name'].lower() == apollo_member['name'].lower():
                                # Update LinkedIn if Apollo has it and member doesn't
                                if not existing_member.get('linkedin_url') and apollo_member.get('linkedin_url'):
                                    existing_member['linkedin_url'] = apollo_member['linkedin_url']
                                    print(f" Added LinkedIn for {existing_member['name']}")
                                
                                # Update Twitter if Apollo has it and member doesn't
                                if not existing_member.get('twitter_url') and apollo_member.get('twitter_url'):
                                    existing_member['twitter_url'] = apollo_member['twitter_url']
                                    print(f" Added Twitter for {existing_member['name']}")

                                # Update email if Apollo has it and member doesn't
                                if not existing_member.get('email') and apollo_member.get('email'):
                                    existing_member['email'] = apollo_member['email']
                                    print(f" Added email for {existing_member['name']}")

                                # Update Apollo person ID if available (for efficient enrichment)
                                if apollo_member.get('apollo_person_id') and not existing_member.get('apollo_person_id'):
                                    existing_member['apollo_person_id'] = apollo_member['apollo_person_id']
                                    print(f" Added Apollo person ID for {existing_member['name']}")
                                
                                # Update role if it was missing
                                if not existing_member.get('role') and apollo_member.get('role'):
                                    existing_member['role'] = apollo_member['role']
                                    print(f" Added role for {existing_member['name']}: {apollo_member['role']}")
                                
                                # Update source to show it came from both
                                if existing_member.get('source') == 'cryptorank_team_page':
                                    existing_member['source'] = 'cryptorank_team_page + apollo_api'
                                    existing_member['source_url'] = f"{existing_member.get('source_url', '')} + {apollo_member.get('source_url', '')}"
                                break
        
        # Add each team member as individual entry with project info
        for member in team:
            person_entry = {
                "name": member['name'],
                "role": member.get('role'),
                "linkedin_url": member.get('linkedin_url'),
                "twitter_url": member.get('twitter_url'),
                "apollo_person_id": member.get('apollo_person_id'),
                "source": member.get('source', 'cryptorank_team_page'),
                "source_url": member.get('source_url', ''),
                "project": project['name'],
                "project_url": project['url'],
                "project_source_url": project.get('source_url', 'https://cryptorank.io/funding-rounds'),
                "company_website": website_info['website'] if website_info else None
            }
            all_people.append(person_entry)
        
        # If no team members found, still add project info with website
        if not team:
            print(f" No team members found, adding project info with website")
            person_entry = {
                "name": None,
                "role": None,
                "linkedin_url": None,
                "source": "project_only",
                "source_url": "",
                "project": project['name'],
                "project_url": project['url'],
                "project_source_url": project.get('source_url', 'https://cryptorank.io/funding-rounds'),
                "company_website": website_info['website'] if website_info else None
            }
            all_people.append(person_entry)
        
        print(f" Successfully processed {project['name']} - Added {len(team)} people")
    
    print("\n" + "="*60)
    print(f" COLLECTION COMPLETE!")
    print(f" Total projects processed: {len(projects)}")
    print(f" Total people collected: {len(all_people)}")
    print("="*60 + "\n")
    
    # Email enrichment via Apollo bulk API (costs credits)
    people_to_enrich = [p for p in all_people if p.get('apollo_person_id') or p.get('linkedin_url')]
    if people_to_enrich:
        enrichment_results = enrich_people_with_emails(people_to_enrich)
        enriched_count = 0
        for person in all_people:
            result_key = person.get('apollo_person_id') or person.get('linkedin_url')
            if result_key and result_key in enrichment_results:
                email = enrichment_results[result_key].get('email')
                if email:
                    person['email'] = email
                    enriched_count += 1
        print(f"\n Enrichment complete: Added emails to {enriched_count} people")

    # Telegram username resolution phase (Pass 1: Twitter handles, Pass 2: name patterns)
    people_with_names = [p for p in all_people if p.get('name')]
    if people_with_names:
        twitter_count = sum(1 for p in all_people if p.get('twitter_url'))
        print(f"\n{'='*60}")
        print(f" TELEGRAM PHASE: {twitter_count} Twitter handles + {len(people_with_names)} name-based lookups")
        print(f"{'='*60}\n")
        resolve_telegram_usernames(all_people)
    else:
        print(f"\n No people to check on Telegram")

    return all_people

import json
import pandas as pd
import os
from datetime import datetime

# Slack Configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

def send_error_to_slack(error_message):
    """Send error notification to Slack"""
    print(f"\n Sending error notification to Slack...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        # Send error message
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f" Fundraising Agent Failed: {error_message}"
        )
        
        print(f" Error notification sent to Slack!")
        return True
        
    except Exception as e:
        print(f" Failed to send error notification: {str(e)}")
        return False

LINAUTO_BASE_URL = "http://89.167.80.102:8000/api/v1"
LINAUTO_API_KEY = os.getenv("LINAUTO_API_KEY")
LINAUTO_CAMPAIGN_ID = "24acf14e-82ce-4ccd-826b-95739145d762"

def push_to_linauto(csv_file_path):
    """Create a new lead list, upload CSV, and assign to the campaign."""
    if not LINAUTO_API_KEY:
        print(" LINAUTO_API_KEY not set — skipping Linauto push")
        return False

    list_name = f"Fundraising Agent - {datetime.now().strftime('%m/%d')}"
    headers = {"Authorization": f"Bearer {LINAUTO_API_KEY}"}

    print(f"\n Pushing CSV to Linauto list '{list_name}'...")
    try:
        # 1. Create list
        r = requests.post(
            f"{LINAUTO_BASE_URL}/lead-lists",
            headers={**headers, "Content-Type": "application/json"},
            json={"name": list_name},
            timeout=30,
        )
        if r.status_code == 409:
            # Name collision (same-day re-run) — look up existing list
            lists = requests.get(f"{LINAUTO_BASE_URL}/lead-lists", headers=headers, timeout=30).json()
            existing = next((l for l in lists if l.get("name") == list_name), None)
            if not existing:
                print(f" Linauto: 409 on create but list not found in GET")
                return False
            list_id = existing["id"]
            print(f" ℹ Reusing existing list {list_id}")
        else:
            r.raise_for_status()
            list_id = r.json()["id"]
            print(f" Created list {list_id}")

        # 2. Upload CSV
        with open(csv_file_path, "rb") as f:
            r = requests.post(
                f"{LINAUTO_BASE_URL}/lead-lists/{list_id}/import",
                headers=headers,
                files={"file": f},
                timeout=120,
            )
        r.raise_for_status()
        import_result = r.json()
        print(f" Imported: {import_result}")

        # 3. Assign to campaign
        r = requests.post(
            f"{LINAUTO_BASE_URL}/lead-lists/{list_id}/assign",
            headers={**headers, "Content-Type": "application/json"},
            json={"campaign_id": LINAUTO_CAMPAIGN_ID},
            timeout=30,
        )
        r.raise_for_status()
        print(f" Assigned to campaign: {r.json()}")
        return True
    except Exception as e:
        print(f" Linauto push failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_to_slack(csv_file_path, people_count, projects_count):
    """Send CSV file to Slack channel using Bot API"""
    print(f"\nSending CSV file to Slack channel {SLACK_CHANNEL}...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        # Try different channel formats - ensure we only send once
        channel_formats = [SLACK_CHANNEL, f"#{SLACK_CHANNEL}"]
        file_sent = False
        
        for channel_format in channel_formats:
            if file_sent:
                break # Ensure we only send once
                
            try:
                print(f" Trying channel format: '{channel_format}'")
                # Upload the CSV file with a descriptive message
                response = client.files_upload_v2(
                    channel=channel_format,
                    file=csv_file_path,
                    title="New Fundraising Leads Available",
                    initial_comment=f"Fundraising Agent Success! Found {people_count} people from {projects_count} projects. Check the uploaded CSV file for details."
                )
                
                print(f" File successfully uploaded to Slack!")
                print(f" File URL: {response['file']['permalink']}")
                file_sent = True
                return True
                
            except SlackApiError as e:
                error_msg = e.response.get('error', 'Unknown error')
                print(f" Channel '{channel_format}' failed: {error_msg}")
                if error_msg == 'channel_not_found':
                    continue # Try next format
                else:
                    raise # Re-raise other errors
        
        # If we get here, all channel formats failed
        if not file_sent:
            print(f" All channel formats failed")
        return False
        
    except SlackApiError as e:
        error_msg = e.response.get('error', 'Unknown error')
        print(f" Slack API Error: {error_msg}")
        
        if error_msg == 'missing_scope':
            print(f" Your token needs 'files:write' and 'chat:write' scopes")
            print(f" Visit: https://api.slack.com/apps Your App OAuth & Permissions")
        elif error_msg == 'not_in_channel':
            print(f" Invite the bot to #{SLACK_CHANNEL}: /invite @YourBotName")
        elif error_msg == 'channel_not_found':
            print(f" Channel #{SLACK_CHANNEL} not found or bot not invited")
            print(f" Invite the bot: /invite @YourBotName to #{SLACK_CHANNEL}")
        elif error_msg == 'invalid_auth':
            print(f" Token appears to be invalid or expired")
        
        print(f" CSV file is still available locally: {csv_file_path}")
        return False
    except ImportError:
        print(f"Slack SDK not installed. Install with: pip install slack-sdk")
        return False
    except Exception as e:
        print(f" Error sending to Slack: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# Crypto Fundraising Agent")
    print("# Sources: CryptoRank + RootData + Apollo.io")
    print("#"*60)
    
    try:
        people = gather_all()
        
        if not people:
            print(f" WARNING: No data collected. Check the logs above.")
        else:
            # Create dated folder
            current_date = datetime.now().strftime("%m-%d")
            folder_name = f"Fundraises - {current_date}"
            
            print(f"\n Creating folder: {folder_name}")
            os.makedirs(folder_name, exist_ok=True)
            print(f" Folder created successfully")
            
            # Save JSON
            file_basename = datetime.now().strftime("%m-%d")
            json_path = os.path.join(folder_name, f"{file_basename}.json")
            print(f"\n Saving data to '{json_path}'...")
            with open(json_path, "w") as f:
                json.dump(people, f, indent=2)
            print(f" JSON saved: {len(people)} people")
            
            # Convert to CSV
            print(f"\n Converting to CSV...")
            df = pd.DataFrame(people)
            
            # Ensure role names are properly included in CSV
            if 'role' in df.columns:
                df['role'] = df['role'].fillna('No Role Found')
                print(f" Role names included in CSV output")
            else:
                print(f"  No role column found in data")
            
            # Order columns so telegram_username sits next to twitter_url
            preferred_order = [
                'name', 'role', 'linkedin_url', 'twitter_url', 'telegram_username',
                'email', 'apollo_person_id', 'source', 'source_url',
                'project', 'project_url', 'project_source_url', 'company_website'
            ]
            ordered_cols = [c for c in preferred_order if c in df.columns]
            ordered_cols += [c for c in df.columns if c not in ordered_cols]
            df = df[ordered_cols]

            csv_filename = os.path.join(folder_name, f"{file_basename}.csv")
            df.to_csv(csv_filename, index=False)
            print(f" CSV saved: {csv_filename}")
            
            # Display summary
            print(f"\n SUMMARY:")
            print(f" Total people: {len(people)}")
            cryptorank_team_count = sum(1 for p in people if 'cryptorank_team_page' in p.get('source', ''))
            apollo_count = sum(1 for p in people if 'apollo_api' in p.get('source', ''))
            rootdata_count = sum(1 for p in people if 'rootdata' in p.get('source', ''))
            project_only_count = sum(1 for p in people if p.get('source') == 'project_only')
            combined_count = sum(1 for p in people if '+' in p.get('source', ''))
            print(f" From CryptoRank Team Pages: {cryptorank_team_count}")
            print(f" From RootData: {rootdata_count}")
            print(f" From Apollo API: {apollo_count}")
            print(f" Combined Sources: {combined_count}")
            print(f" Project Data Only: {project_only_count}")
            print(f" Files saved in: {folder_name}/")
            
            # Send to Slack
            unique_projects = len(set(p.get('project') for p in people if p.get('project')))
            slack_success = send_to_slack(csv_filename, len(people), unique_projects)

            # Push to Linauto (independent of Slack outcome)
            push_to_linauto(csv_filename)

            if not slack_success:
                print("Slack upload failed, but data was saved locally")
    
    except Exception as e:
        error_message = f"FATAL ERROR: {str(e)}"
        print(f"\n {error_message}")
        import traceback
        traceback.print_exc()
        
        # Send error notification to Slack
        try:
            send_error_to_slack(error_message)
        except:
            print(" Failed to send error notification to Slack")
        
        # Re-raise the exception to fail the GitHub Action
        raise
    
    print("\n" + "#"*60)
    print("# Script execution finished")
    print("#"*60 + "\n")

