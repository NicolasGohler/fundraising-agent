from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import requests
import re

# Apollo.io API Configuration
APOLLO_API_KEY = "oiiVIE2ufVWw3euhP3XLgA"
APOLLO_API_URL = "https://api.apollo.io/v1/mixed_people/search"

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
        max_projects = 20
        
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
                
                if href in seen_urls:
                    continue
                
                seen_urls.add(href)
                projects.append({"name": text.strip(), "url": href})
                
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
        max_projects = 20
        
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
                    "source": "rootdata"
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
                "source": project.get('source', 'cryptorank')
            })
    
    print(f"\n{'='*60}")
    print(f"📊 MERGED PROJECTS FROM ALL SOURCES")
    print(f"   CryptoRank: {len(cryptorank_projects)} projects")
    print(f"   RootData: {len(rootdata_projects)} projects")
    print(f"   Total unique: {len(all_projects)} projects")
    print(f"{'='*60}\n")
    
    return all_projects

def fetch_team_from_apollo(company_name):
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
        "Director", "Managing Director"
    ]
    
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
                
                member_data = {
                    "name": name,
                    "role": title if title else None,
                    "linkedin_url": linkedin_url,
                    "source": "apollo"
                }
                members.append(member_data)
                
                linkedin_str = "with LinkedIn" if linkedin_url else "no LinkedIn"
                print(f"   ✅ {len(members)}. {name} - {title if title else 'No role'}, {linkedin_str}")
            
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
                    "source": "cryptorank"
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
        
        # Only try CryptoRank team page if project is from CryptoRank
        if project['source'] == 'cryptorank':
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
        
        # Apollo fallback
        if should_use_apollo:
            time.sleep(2)
            apollo_team = fetch_team_from_apollo(project['name'])
            
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
                                
                                # Update role if it was missing
                                if not existing_member.get('role') and apollo_member.get('role'):
                                    existing_member['role'] = apollo_member['role']
                                    print(f"   📝 Added role for {existing_member['name']}: {apollo_member['role']}")
                                
                                # Update source to show it came from both
                                if existing_member.get('source') == 'cryptorank':
                                    existing_member['source'] = 'cryptorank + apollo'
                                break
        
        # Add each team member as individual entry with project info
        for member in team:
            # Determine final source value
            member_source = member.get('source', 'apollo')
            if member_source == 'apollo' and project['source'] == 'rootdata':
                member_source = 'rootdata + apollo'
            
            person_entry = {
                "name": member['name'],
                "role": member.get('role'),
                "linkedin_url": member.get('linkedin_url'),
                "source": member_source,
                "project": project['name'],
                "project_url": project['url']
            }
            all_people.append(person_entry)
        
        print(f"✅ Successfully processed {project['name']} - Added {len(team)} people")
    
    print("\n" + "="*60)
    print(f"🎉 COLLECTION COMPLETE!")
    print(f"   Total projects processed: {len(projects)}")
    print(f"   Total people collected: {len(all_people)}")
    print("="*60 + "\n")
    
    return all_people

import json
import pandas as pd
import os
from datetime import datetime

# Slack Configuration
SLACK_BOT_TOKEN = "xoxb-5736340339410-9698047778609-dqUa7c0cxcQyM7zdz2bcUPnm"
SLACK_CHANNEL = "C09CKTZ61DK"

def send_to_slack(csv_file_path):
    """Send CSV file to Slack channel using Bot API"""
    print(f"\n📤 Sending CSV file to Slack channel {SLACK_CHANNEL}...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        # Try different channel formats
        channel_formats = [SLACK_CHANNEL, f"#{SLACK_CHANNEL}"]
        
        for channel_format in channel_formats:
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
                return True
                
            except SlackApiError as e:
                error_msg = e.response.get('error', 'Unknown error')
                print(f"   ❌ Channel '{channel_format}' failed: {error_msg}")
                if error_msg == 'channel_not_found':
                    continue  # Try next format
                else:
                    raise  # Re-raise other errors
        
        # If we get here, all channel formats failed
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

def test_slack_file_upload():
    """Test function to send CSV file to Slack without running full system"""
    print("🧪 Testing Slack Bot API file upload...")
    
    # Check if CSV exists
    csv_file = "funding_data.csv"
    if not os.path.exists(csv_file):
        print(f"❌ CSV file {csv_file} not found. Run the main script first.")
        return False
    
    # Send the file
    return send_to_slack(csv_file)

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# Crypto Fundraising Team Scraper")
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
            csv_filename = os.path.join(folder_name, "funding_data.csv")
            df.to_csv(csv_filename, index=False)
            print(f"✅ CSV saved: {csv_filename}")
            
            # Display summary
            print(f"\n📈 SUMMARY:")
            print(f"   Total people: {len(people)}")
            cryptorank_count = sum(1 for p in people if 'cryptorank' in p.get('source', ''))
            apollo_count = sum(1 for p in people if 'apollo' in p.get('source', ''))
            rootdata_count = sum(1 for p in people if 'rootdata' in p.get('source', ''))
            print(f"   From CryptoRank: {cryptorank_count}")
            print(f"   From RootData: {rootdata_count}")
            print(f"   From Apollo: {apollo_count}")
            print(f"   📁 Files saved in: {folder_name}/")
            
            # Send to Slack
            send_to_slack(csv_filename)
    
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "#"*60)
    print("# Script execution finished")
    print("#"*60 + "\n")

