from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import requests
import re
from urllib.parse import urlparse
import json
import os

# Configuration
MAX_PROJECTS = 15  # Maximum projects to collect from each source (reduced by 10%)

# Apollo.io API Configuration
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "oiiVIE2ufVWw3euhP3XLgA")
APOLLO_API_URL = "https://api.apollo.io/v1/mixed_people/search"
APOLLO_BULK_ENRICHMENT_URL = "https://api.apollo.io/api/v1/people/bulk_match"

def get_projects_from_cryptorank():
    """Fetch projects from CryptoRank funding rounds"""
    url = "https://cryptorank.io/funding-rounds"
    print(f"\n{'='*60}")
    print(f"🔍 SOURCE 1: Fetching projects from CryptoRank")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("⏳ Loading page...")
        page.goto(url, wait_until="networkidle")
        print("✅ Page loaded successfully")
        
        print("⏳ Waiting for table rows to load...")
        try:
            page.wait_for_selector("a[href*='/ico/']", timeout=10000)
            print("✅ Found project links!")
        except Exception as e:
            print(f"⚠️  Timeout waiting for project links: {str(e)}")
            print("   The page might use different structure")
        
        time.sleep(5)
        print("⏳ Waited additional 5 seconds for complete rendering")
        
        print("\n🔍 Searching for project links using Playwright...")
        project_links = page.locator("a[href*='/ico/']").all()
        print(f"   Found {len(project_links)} potential project links")
        
        projects = []
        seen_urls = set()
        max_projects = MAX_PROJECTS
        
        for idx, link in enumerate(project_links):
            if len(projects) >= max_projects:
                print(f"   ⏸️  Collected {max_projects} projects, stopping collection")
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
                    print(f"   🔄 Converted ICO URL to price URL: {href}")
                
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
                print(f"   ⚠️  Error processing link {idx}: {str(e)}")
                continue
        
        browser.close()
        
        print(f"\n{'='*60}")
        print(f"✅ Total unique projects found: {len(projects)}")
        print(f"{'='*60}\n")
        
        return projects

def get_projects_from_rootdata():
    """Fetch projects from RootData fundraising page"""
    url = "https://www.rootdata.com/Fundraising"
    print(f"\n{'='*60}")
    print(f"🔍 SOURCE 2: Fetching projects from RootData")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("⏳ Loading page...")
        page.goto(url, wait_until="networkidle")
        print("✅ Page loaded successfully")
        
        time.sleep(5)
        print("⏳ Waited 5 seconds for JavaScript to render")
        
        print("\n🔍 Searching for project links...")
        project_links = page.locator("a[href*='/Projects/detail/']").all()
        print(f"   Found {len(project_links)} potential project links")
        
        projects = []
        seen_names = set()
        max_projects = MAX_PROJECTS
        
        for idx, link in enumerate(project_links):
            if len(projects) >= max_projects:
                print(f"   ⏸️  Collected {max_projects} projects, stopping collection")
                break
            
            try:
                href = link.get_attribute("href")
                text = link.inner_text()
                
                if not href or not text.strip():
                    continue
                
                if not href.startswith("http"):
                    href = "https://www.rootdata.com" + href
                
                # Use name as key to avoid duplicates
                clean_name = text.strip().split('\n')[0]
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
                print(f"   ⚠️  Error processing link {idx}: {str(e)}")
                continue
        
        browser.close()
        
        print(f"\n{'='*60}")
        print(f"✅ Total RootData projects found: {len(projects)}")
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
        
        if name_key not in seen_names and len(clean_name) > 1:
            seen_names.add(name_key)
            all_projects.append({
                "name": clean_name,
                "url": project['url'],
                "source": project.get('source', 'cryptorank_funding_rounds'),
                "source_url": project.get('source_url', 'https://cryptorank.io/funding-rounds'),
                "source_type": project.get('source_type', 'funding_platform')
            })
    
    print(f"\n{'='*60}")
    print(f"📊 MERGED PROJECTS FROM ALL SOURCES")
    print(f"   CryptoRank: {len(cryptorank_projects)} projects")
    print(f"   RootData: {len(rootdata_projects)} projects")
    print(f"   Total unique: {len(all_projects)} projects")
    print(f"{'='*60}\n")
    
    return all_projects

def extract_company_website(project_url):
    """Extract company website from main project page (not ICO/team pages)"""
    print(f"\n🌐 Extracting company website from main project page: {project_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(project_url, wait_until="networkidle", timeout=15000)
            print("✅ Main project page loaded")
            
            time.sleep(3)  # Give more time for dynamic content
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            website = None
            
            # For CryptoRank: Look for website link in the Links section
            if 'cryptorank.io' in project_url:
                print("   🔍 Looking for website in CryptoRank Links section...")
                
                # Look for the "Links" section with multiple approaches
                links_section = None
                
                # First, try to find the exact "Links" text (not containing "Links")
                links_text = soup.find(text=lambda text: text and text.strip() == 'Links')
                if links_text:
                    links_section = links_text.parent
                    print(f"   ✅ Found exact 'Links' text in {links_section.name}")
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
                    print("   ✅ Found 'Links' section")
                    # Find the parent container of the Links section
                    links_container = links_section.find_parent()
                    if links_container:
                        # Look for the "Website" button specifically with more comprehensive search
                        website_buttons = links_container.find_all('a', href=True)
                        print(f"   Found {len(website_buttons)} links in Links section")
                        
                        for link in website_buttons:
                            href = link.get('href', '')
                            text = link.get_text(strip=True).lower()
                            
                            print(f"   Checking link: '{text}' -> {href}")
                            
                            # Look specifically for the "Website" button - improved matching
                            if ('website' in text or 'site' in text) and href.startswith('http'):
                                # Additional validation to ensure it's not a social media link
                                if not any(social in href.lower() for social in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'breakingthenews.net']):
                                    website = href
                                    print(f"   ✅ Found Website button: {href}")
                                    break
                
                # If no website found in Links section, look for sibling elements
                if not website and links_section:
                    print("   🔍 No website in Links section, checking sibling elements...")
                    links_parent = links_section.find_parent()
                    if links_parent:
                        # Look for sibling divs that might contain the links
                        siblings = links_parent.find_next_siblings()
                        for sibling in siblings:
                            if sibling.name == 'div':
                                sibling_links = sibling.find_all('a', href=True)
                                print(f"   Found {len(sibling_links)} links in sibling div")
                                
                                for link in sibling_links:
                                    href = link.get('href', '')
                                    text = link.get_text(strip=True).lower()
                                    
                                    print(f"   Checking sibling link: '{text}' -> {href}")
                                    
                                    # Look for website links
                                    if ('website' in text or 'site' in text) and href.startswith('http'):
                                        if not any(social in href.lower() for social in ['twitter', 'telegram', 'discord', 'medium', 'github', 'youtube', 'linkedin', 'facebook', 'instagram', 'x.com', 'breakingthenews.net']):
                                            website = href
                                            print(f"   ✅ Found Website in sibling: {href}")
                                            break
                                if website:
                                    break
                
                # If still no website found, try looking for the Links section more broadly
                if not website:
                    print("   🔍 Trying broader search for Links section...")
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
                                    print(f"   ✅ Found Website in broader search: {href}")
                                    break
                        if website:
                            break
                
                # If no Website button found in Links section, try broader search
                if not website:
                    print("   🔍 No Website button found, trying broader search...")
                    all_links = soup.find_all('a', href=True)
                    print(f"   Found {len(all_links)} total links on page")
                    
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
                        print(f"   ✅ Found potential website: {website}")
                    else:
                        print("   ⚠️  No suitable website found")
            
            # For RootData: Look for website link in project details
            elif 'rootdata.com' in project_url:
                print("   🔍 Looking for website in RootData project details...")
                
                # Use longer timeout for RootData pages
                try:
                    page.goto(project_url, wait_until="load", timeout=20000)
                    time.sleep(3)
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    print("   ✅ RootData page loaded successfully")
                except:
                    print("   ⚠️  RootData page load failed, using existing content")
                
                # Look for website links in the main content area
                website_links = soup.find_all('a', href=True)
                print(f"   Found {len(website_links)} links on RootData page")
                
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
                            print(f"   ✅ Found company website link: {href}")
                            break
            
            browser.close()
            
            if website:
                # Filter out telegram URLs - they're not valid company websites
                if 't.me' in website.lower() or 'telegram' in website.lower():
                    print(f"⚠️  Found telegram URL instead of website: {website}")
                    print("   Skipping - telegram URLs are not valid for Apollo enrichment")
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
                        print(f"⚠️  Domain appears to be telegram: {domain}")
                        print("   Skipping - telegram domains are not valid for Apollo enrichment")
                        return None
                    
                    print(f"✅ Successfully found website: {website} (domain: {domain})")
                    return {"website": website, "domain": domain}
                except:
                    print(f"⚠️  Could not parse website URL: {website}")
                    return None
            else:
                print("⚠️  No company website found on main project page")
                return None
                
        except Exception as e:
            print(f"❌ Error extracting website: {str(e)}")
            browser.close()
            return None

def fetch_team_from_apollo(company_name, company_website=None):
    """Apollo.io API fallback for team members"""
    print(f"\n{'='*60}")
    print(f"🔍 APOLLO FALLBACK: Searching for {company_name} team on Apollo.io")
    print(f"{'='*60}")
    
    clean_name = re.sub(r'\$.*', '', company_name).strip()
    clean_name = re.sub(r'\n.*', '', clean_name).strip()
    print(f"   Cleaned company name: '{clean_name}'")
    
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY
    }
    
    target_titles = [
        "CEO", "CFO", "COO", "Chief",
        "Co-Founder", "Founder", "Co Founder",
        "VP", "Vice President", "V.P.",
        "Director", "Managing Director",
        "General Manager", "Growth",
        "Chief of Staff"
    ]
    
    # Use website domain for more accurate search if available
    if company_website and company_website.get('domain'):
        domain = company_website['domain']
        print(f"   Using website domain for search: '{domain}'")
        payload = {
            "q_organization_domain": domain,
            "person_titles": target_titles,
            "page": 1,
            "per_page": 25
        }
    else:
        print(f"   Using company name for search: '{clean_name}'")
    payload = {
        "q_organization_name": clean_name,
        "person_titles": target_titles,
        "page": 1,
        "per_page": 25
    }
    
    members = []
    
    try:
        response = requests.post(APOLLO_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            people = data.get('people', [])
            
            print(f"   ✅ Apollo found {len(people)} team members")
            
            for person in people:
                name = person.get('name')
                if not name:
                    continue
                name = name.strip()
                
                title = person.get('title')
                title = title.strip() if title else None
                
                # Exclude CTOs
                if title and ('cto' in title.lower() or 'chief technology' in title.lower()):
                    continue
                
                linkedin_url = person.get('linkedin_url')
                if linkedin_url and linkedin_url.startswith('http://'):
                    linkedin_url = linkedin_url.replace('http://', 'https://')
                
                # Store Apollo person ID for efficient enrichment later
                apollo_person_id = person.get('id') or person.get('person_id') or person.get('apollo_id')
                
                member_data = {
                    "name": name,
                    "role": title if title else None,
                    "linkedin_url": linkedin_url,
                    "apollo_person_id": apollo_person_id,  # Store for efficient enrichment
                    "source": "apollo_api",
                    "source_url": "https://api.apollo.io/v1/mixed_people/search",
                    "source_type": "people_database",
                    "apollo_search_method": "domain" if company_website and company_website.get('domain') else "company_name"
                }
                members.append(member_data)
                
                linkedin_str = "with LinkedIn" if linkedin_url else "no LinkedIn"
                id_str = f" (ID: {apollo_person_id})" if apollo_person_id else ""
                print(f"   ✅ {len(members)}. {name} - {title if title else 'No role'}, {linkedin_str}{id_str}")
            
            print(f"\n✅ Apollo returned {len(members)} team members")
            
        elif response.status_code == 429:
            print(f"   ⚠️  Rate limit reached on Apollo API")
        elif response.status_code == 401:
            print(f"   ❌ Apollo API authentication failed - check API key")
        else:
            print(f"   ⚠️  Apollo API returned status {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Apollo API request timed out")
    except Exception as e:
        print(f"   ❌ Error with Apollo API: {str(e)}")
    
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
    print(f"📧 APOLLO BULK ENRICHMENT: Enriching {len(people_with_linkedin)} people with emails")
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
            print(f"   ⚠️  Skipping {person.get('name', 'Unknown')}: Invalid URL (telegram link)")
            skipped_count += 1
            continue
        
        valid_people.append(person)
    
    if skipped_count > 0:
        print(f"   ℹ️  Filtered out {skipped_count} invalid entries")
    
    if not valid_people:
        print(f"   ⚠️  No valid people to enrich after filtering")
        return {}
    
    print(f"   ✅ Processing {len(valid_people)} valid people for enrichment")
    
    for i in range(0, len(valid_people), batch_size):
        batch = valid_people[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(valid_people) + batch_size - 1) // batch_size
        
        print(f"\n   Processing batch {batch_num}/{total_batches} ({len(batch)} people)...")
        
        # Prepare details array for Apollo API
        details = []
        batch_mapping = []  # Store person info for result mapping
        
        for person in batch:
            apollo_person_id = person.get('apollo_person_id')
            linkedin_url = person.get('linkedin_url')
            
            detail = {}
            
            # Prefer Apollo person ID for better matches (when available)
            if apollo_person_id:
                detail["person_id"] = apollo_person_id
                print(f"      Using Apollo person ID for {person.get('name', 'Unknown')}")
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
                
                print(f"      Using LinkedIn URL for {person.get('name', 'Unknown')}")
            else:
                # Skip if no identifier
                continue
            
            details.append(detail)
            batch_mapping.append(person)
        
        if not details:
            print(f"   ⚠️  No valid identifiers in batch, skipping...")
            continue
        
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }
        
        payload = {
            "api_key": APOLLO_API_KEY,
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
                
                print(f"   ✅ Apollo returned {len(matches)} enriched matches")
                
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
                                print(f"   ✅ {person.get('name', 'Unknown')} ({method_str}): {email}")
                            else:
                                print(f"   ⚠️  {person.get('name', 'Unknown')}: No email found")
                
            elif response.status_code == 429:
                print(f"   ⚠️  Rate limit reached on Apollo API, waiting 60 seconds...")
                time.sleep(60)
            elif response.status_code == 401:
                print(f"   ❌ Apollo API authentication failed - check API key")
                break
            else:
                print(f"   ⚠️  Apollo API returned status {response.status_code}: {response.text[:200]}")
            
            # Add delay between batches to respect rate limits
            if i + batch_size < len(people_with_linkedin):
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            print(f"   ⚠️  Apollo API request timed out")
        except Exception as e:
            print(f"   ❌ Error with Apollo bulk enrichment API: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ Bulk enrichment complete: {len(enrichment_results)} people enriched with emails")
    return enrichment_results

def fetch_team_members(project_url):
    print(f"\n{'='*60}")
    print(f"👥 STEP 2: Fetching team members from {project_url}")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Convert /ico/ URLs to /price/.../team format
        team_url = project_url.replace('/ico/', '/price/') 
        if not team_url.endswith('/team'):
            team_url = team_url.split('#')[0]
            team_url = team_url.rstrip('/') + '/team'
        
        print(f"⏳ Loading team page: {team_url}")
        try:
            page.goto(team_url, wait_until="networkidle", timeout=15000)
            print("✅ Team page loaded")
        except Exception as e:
            print(f"❌ Error loading team page: {str(e)}")
            browser.close()
            return []
        
        time.sleep(3)
        print("⏳ Waited 3 seconds for JavaScript to render")
        
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        print("\n🔍 Searching for team members...")
        members = []
        
        try:
            # Team member names are in <p> tags with 'bvzmmt' class
            name_tags = soup.find_all('p', class_=lambda x: x and 'bvzmmt' in x)
            print(f"   Found {len(name_tags)} potential team member elements")
            
            name_pattern = re.compile(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,3}$')
            
            for name_tag in name_tags:
                name = name_tag.get_text(strip=True)
                
                if not name_pattern.match(name):
                    continue
                
                parent = name_tag.find_parent()
                role = None
                linkedin_url = None
                
                if parent:
                    next_p = name_tag.find_next_sibling('p')
                    if next_p:
                        potential_role = next_p.get_text(strip=True)
                        if potential_role and len(potential_role) < 50 and not name_pattern.match(potential_role):
                            role = potential_role
                    
                    # Find LinkedIn URL in great-grandparent container
                    grandparent = parent.find_parent()
                    if grandparent:
                        great_grandparent = grandparent.find_parent()
                        if great_grandparent:
                            for a in great_grandparent.find_all('a', href=True):
                                href = a['href']
                                if 'linkedin.com' in href.lower():
                                    linkedin_url = href
                                    break
                
                # Exclude CTOs
                if role and ('cto' in role.lower() or 'chief technology' in role.lower()):
                    continue
                
                member_data = {
                    "name": name,
                    "role": role,
                    "linkedin_url": linkedin_url,
                    "source": "cryptorank_team_page",
                    "source_url": team_url,
                    "source_type": "project_team_page"
                }
                members.append(member_data)
                
                linkedin_str = "with LinkedIn" if linkedin_url else "no LinkedIn"
                print(f"   ✅ {len(members)}. {name} - {role if role else 'No role found'}, {linkedin_str}")
        
        except Exception as e:
            print(f"❌ Error parsing team members: {str(e)}")
            import traceback
            traceback.print_exc()
        
        browser.close()
        
        print(f"\n✅ Total team members found: {len(members)}")
        return members

def gather_all():
    """Main function to gather all team members from all sources"""
    print("\n" + "="*60)
    print("🚀 STARTING DATA COLLECTION PROCESS")
    print("="*60)
    
    projects = get_all_projects()
    
    if not projects:
        print("\n❌ ERROR: No projects found! Cannot continue.")
        return []
    
    all_people = []
    print(f"\n📋 Processing all {len(projects)} projects\n")

    for idx, project in enumerate(projects, 1):
        print(f"\n{'='*60}")
        print(f"🔄 Processing {idx}/{len(projects)}: {project['name']}")
        print(f"   Source: {project['source']}")
        print(f"{'='*60}")
        
        team = []
        
        # Extract company website first
        website_info = extract_company_website(project['url'])
        
        # Use Apollo directly when website found to save resources
        if website_info and website_info.get('domain'):
            print(f"   ✅ Website found! Using Apollo with domain: {website_info['domain']}")
            team = []
            should_use_apollo = True
        else:
            # Fallback to original method if no website found
            print("   ⚠️  No website found, using fallback method")
            
            # Only try CryptoRank team page if project is from CryptoRank
            if project['source'] == 'cryptorank_funding_rounds':
                team = fetch_team_members(project['url'])
            else:
                print("   ℹ️  RootData project - skipping team page, will use Apollo")
            
            # Determine if Apollo is needed
            should_use_apollo = False
            
            if not team:
                print("   ⚠️  No team members found - will try Apollo")
                should_use_apollo = True
            else:
                members_without_linkedin = [m for m in team if not m.get('linkedin_url')]
                if members_without_linkedin:
                    print(f"   ⚠️  {len(members_without_linkedin)} team member(s) have no LinkedIn - will try Apollo")
                    should_use_apollo = True
        
        # Apollo search
        if should_use_apollo:
            time.sleep(2)
            apollo_team = fetch_team_from_apollo(project['name'], website_info)
            
            if apollo_team:
                existing_names = {m['name'].lower() for m in team}
                
                for apollo_member in apollo_team:
                    apollo_role = apollo_member.get('role', '')
                    if apollo_role and ('cto' in apollo_role.lower() or 'chief technology' in apollo_role.lower()):
                        continue
                    
                    if apollo_member['name'].lower() not in existing_names:
                        team.append(apollo_member)
                        print(f"   ➕ Added from Apollo: {apollo_member['name']}")
                    else:
                        for existing_member in team:
                            if existing_member['name'].lower() == apollo_member['name'].lower():
                                # Update LinkedIn if Apollo has it and member doesn't
                                if not existing_member.get('linkedin_url') and apollo_member.get('linkedin_url'):
                                    existing_member['linkedin_url'] = apollo_member['linkedin_url']
                                    print(f"   🔗 Added LinkedIn for {existing_member['name']}")
                                
                                # Update Apollo person ID if available (for efficient enrichment)
                                if apollo_member.get('apollo_person_id') and not existing_member.get('apollo_person_id'):
                                    existing_member['apollo_person_id'] = apollo_member['apollo_person_id']
                                    print(f"   🆔 Added Apollo person ID for {existing_member['name']}")
                                
                                # Update role if it was missing
                                if not existing_member.get('role') and apollo_member.get('role'):
                                    existing_member['role'] = apollo_member['role']
                                    print(f"   📝 Added role for {existing_member['name']}: {apollo_member['role']}")
                                
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
                "apollo_person_id": member.get('apollo_person_id'),  # Preserve Apollo person ID for efficient enrichment
                "source": member.get('source', 'cryptorank_team_page'),
                "source_url": member.get('source_url', ''),
                "source_type": member.get('source_type', 'project_team_page'),
                "apollo_search_method": member.get('apollo_search_method', ''),
                "project": project['name'],
                "project_url": project['url'],
                "project_source": project.get('source', 'cryptorank_funding_rounds'),
                "project_source_url": project.get('source_url', 'https://cryptorank.io/funding-rounds'),
                "project_source_type": project.get('source_type', 'funding_platform'),
                "company_website": website_info['website'] if website_info else None,
                "company_domain": website_info['domain'] if website_info else None
            }
            all_people.append(person_entry)
        
        # If no team members found, still add project info with website
        if not team:
            print(f"   📝 No team members found, adding project info with website")
            person_entry = {
                "name": None,
                "role": None,
                "linkedin_url": None,
                "source": "project_only",
                "source_url": "",
                "source_type": "project_data_only",
                "apollo_search_method": "",
                "project": project['name'],
                "project_url": project['url'],
                "project_source": project.get('source', 'cryptorank_funding_rounds'),
                "project_source_url": project.get('source_url', 'https://cryptorank.io/funding-rounds'),
                "project_source_type": project.get('source_type', 'funding_platform'),
                "company_website": website_info['website'] if website_info else None,
                "company_domain": website_info['domain'] if website_info else None
            }
            all_people.append(person_entry)
        
        print(f"✅ Successfully processed {project['name']} - Added {len(team)} people")
    
    print("\n" + "="*60)
    print(f"🎉 COLLECTION COMPLETE!")
    print(f"   Total projects processed: {len(projects)}")
    print(f"   Total people collected: {len(all_people)}")
    print("="*60 + "\n")
    
    # Enrich people with Apollo person IDs or LinkedIn URLs using Apollo bulk enrichment
    # Include people with either Apollo person ID (from Apollo API) or LinkedIn URL (from scraping)
    people_to_enrich = [p for p in all_people if p.get('apollo_person_id') or p.get('linkedin_url')]
    if people_to_enrich:
        print(f"\n{'='*60}")
        print(f"📧 ENRICHMENT PHASE: Enriching {len(people_to_enrich)} people with emails")
        print(f"{'='*60}\n")
        
        enrichment_results = enrich_people_with_emails(people_to_enrich)
        
        # Add emails to people records
        enriched_count = 0
        for person in all_people:
            apollo_person_id = person.get('apollo_person_id')
            linkedin_url = person.get('linkedin_url')
            
            # Try person ID first (more efficient), then LinkedIn URL
            result_key = apollo_person_id if apollo_person_id else linkedin_url
            
            if result_key and result_key in enrichment_results:
                email = enrichment_results[result_key].get('email')
                if email:
                    person['email'] = email
                    enriched_count += 1
        
        print(f"\n✅ Enrichment complete: Added emails to {enriched_count} people")
    else:
        print(f"\n⚠️  No people with Apollo person IDs or LinkedIn URLs found, skipping email enrichment")
    
    return all_people

import json
import pandas as pd
import os
from datetime import datetime

# Slack Configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "xoxb-5736340339410-9698047778609-dqUa7c0cxcQyM7zdz2bcUPnm")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "C09CKTZ61DK")

def send_error_to_slack(error_message):
    """Send error notification to Slack"""
    print(f"\n🚨 Sending error notification to Slack...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        # Send error message
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🚨 Fundraising Agent Failed: {error_message}"
        )
        
        print(f"✅ Error notification sent to Slack!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send error notification: {str(e)}")
        return False

def send_success_to_slack(people_count, projects_count):
    """Send success notification to Slack"""
    print(f"\n✅ Sending success notification to Slack...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        # Send success message
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"✅ Fundraising Agent Success! Found {people_count} people from {projects_count} projects. Check the uploaded CSV file for details."
        )
        
        print(f"✅ Success notification sent to Slack!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send success notification: {str(e)}")
        return False


def send_to_slack(csv_file_path):
    """Send CSV file to Slack channel using Bot API"""
    print(f"\n📤 Sending CSV file to Slack channel {SLACK_CHANNEL}...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        # Try different channel formats - ensure we only send once
        channel_formats = [SLACK_CHANNEL, f"#{SLACK_CHANNEL}"]
        file_sent = False
        
        for channel_format in channel_formats:
            if file_sent:
                break  # Ensure we only send once
                
            try:
                print(f"   Trying channel format: '{channel_format}'")
                # Upload the CSV file with a descriptive message
                response = client.files_upload_v2(
                    channel=channel_format,
                    file=csv_file_path,
                    title="🚀 New Fundraising Leads Available",
                    initial_comment="All these people raised in the past week. Make sure you reach out!"
                )
                
                print(f"✅ File successfully uploaded to Slack!")
                print(f"   📁 File URL: {response['file']['permalink']}")
                file_sent = True
                return True
                
            except SlackApiError as e:
                error_msg = e.response.get('error', 'Unknown error')
                print(f"   ❌ Channel '{channel_format}' failed: {error_msg}")
                if error_msg == 'channel_not_found':
                    continue  # Try next format
                else:
                    raise  # Re-raise other errors
        
        # If we get here, all channel formats failed
        if not file_sent:
            print(f"❌ All channel formats failed")
        return False
        
    except SlackApiError as e:
        error_msg = e.response.get('error', 'Unknown error')
        print(f"❌ Slack API Error: {error_msg}")
        
        if error_msg == 'missing_scope':
            print(f"   💡 Your token needs 'files:write' and 'chat:write' scopes")
            print(f"   Visit: https://api.slack.com/apps → Your App → OAuth & Permissions")
        elif error_msg == 'not_in_channel':
            print(f"   💡 Invite the bot to #{SLACK_CHANNEL}: /invite @YourBotName")
        elif error_msg == 'channel_not_found':
            print(f"   💡 Channel #{SLACK_CHANNEL} not found or bot not invited")
            print(f"   💡 Invite the bot: /invite @YourBotName to #{SLACK_CHANNEL}")
        elif error_msg == 'invalid_auth':
            print(f"   💡 Token appears to be invalid or expired")
        
        print(f"   📁 CSV file is still available locally: {csv_file_path}")
        return False
    except ImportError:
        print(f"⚠️  Slack SDK not installed. Install with: pip install slack-sdk")
        return False
    except Exception as e:
        print(f"❌ Error sending to Slack: {str(e)}")
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
            print(f"⚠️  WARNING: No data collected. Check the logs above.")
        else:
            # Create dated folder
            current_date = datetime.now().strftime("%m-%d")
            folder_name = f"Fundraises - {current_date}"
            
            print(f"\n📁 Creating folder: {folder_name}")
            os.makedirs(folder_name, exist_ok=True)
            print(f"✅ Folder created successfully")
            
            # Save JSON
            json_path = os.path.join(folder_name, "funding_data.json")
            print(f"\n💾 Saving data to '{json_path}'...")
            with open(json_path, "w") as f:
                json.dump(people, f, indent=2)
            print(f"✅ JSON saved: {len(people)} people")
            
            # Convert to CSV
            print(f"\n📊 Converting to CSV...")
            df = pd.DataFrame(people)
            
            # Ensure role names are properly included in CSV
            if 'role' in df.columns:
                df['role'] = df['role'].fillna('No Role Found')
                print(f"   ✅ Role names included in CSV output")
            else:
                print(f"   ⚠️  No role column found in data")
            
            csv_filename = os.path.join(folder_name, "funding_data.csv")
            df.to_csv(csv_filename, index=False)
            print(f"✅ CSV saved: {csv_filename}")
            
            # Display summary
            print(f"\n📈 SUMMARY:")
            print(f"   Total people: {len(people)}")
            cryptorank_team_count = sum(1 for p in people if 'cryptorank_team_page' in p.get('source', ''))
            apollo_count = sum(1 for p in people if 'apollo_api' in p.get('source', ''))
            rootdata_count = sum(1 for p in people if 'rootdata' in p.get('source', ''))
            project_only_count = sum(1 for p in people if p.get('source') == 'project_only')
            combined_count = sum(1 for p in people if '+' in p.get('source', ''))
            print(f"   From CryptoRank Team Pages: {cryptorank_team_count}")
            print(f"   From RootData: {rootdata_count}")
            print(f"   From Apollo API: {apollo_count}")
            print(f"   Combined Sources: {combined_count}")
            print(f"   Project Data Only: {project_only_count}")
            print(f"   📁 Files saved in: {folder_name}/")
            
            # Send to Slack
            slack_success = send_to_slack(csv_filename)
            
            # Send success notification
            if slack_success:
                # Count unique projects from the people data
                unique_projects = len(set(p.get('project') for p in people if p.get('project')))
                send_success_to_slack(len(people), unique_projects)
            else:
                print("⚠️  Slack upload failed, but data was saved locally")
    
    except Exception as e:
        error_message = f"FATAL ERROR: {str(e)}"
        print(f"\n❌ {error_message}")
        import traceback
        traceback.print_exc()
        
        # Send error notification to Slack
        try:
            send_error_to_slack(error_message)
        except:
            print("❌ Failed to send error notification to Slack")
        
        # Re-raise the exception to fail the GitHub Action
        raise
    
    print("\n" + "#"*60)
    print("# Script execution finished")
    print("#"*60 + "\n")

