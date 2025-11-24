from flask import Flask, render_template, request, jsonify
import requests
import re

app = Flask(__name__)

def extract_links(url):
    try:
        # Step 1: Get the HubCloud page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        session = requests.Session()
        session.headers.update(headers)
        
        response = session.get(url)
        response.raise_for_status()
        
        # Step 2: Find the "Generate Direct Download Link" (gamerxyt.com)
        match = re.search(r'href="(https://gamerxyt\.com/hubcloud\.php\?[^"]+)"', response.text)
        if not match:
            return {"error": "Could not find intermediate link on HubCloud page."}
        
        intermediate_url = match.group(1)
        
        # Step 3: Get the intermediate page
        response_intermediate = session.get(intermediate_url)
        response_intermediate.raise_for_status()
        
        links = []
        
        # 1. FSL Server
        # Logic: fsl.href += '1' + new Date().getMinutes();
        fsl_match = re.search(r'href="([^"]+r2\.dev[^"]+)" id="fsl"', response_intermediate.text)
        if fsl_match:
            fsl_url = fsl_match.group(1)
            from datetime import datetime
            # Javascript new Date().getMinutes() returns 0-59. 
            # We need to match the client-side logic: '1' + minutes
            minutes = datetime.now().minute
            fsl_url += f"1{minutes}"
            links.append({"name": "FSL Server (Direct)", "url": fsl_url})

        # 2. HubCDN link (10Gbps)
        # Match generic hubcdn.fans domain
        hubcdn_match = re.search(r'href="(https://[^"]+\.hubcdn\.fans/\?id=[^"]+)"', response_intermediate.text)
        if hubcdn_match:
            hubcdn_url = hubcdn_match.group(1)
            # Try to follow redirects for Google Link, but keep HubCDN link if it fails or as alternative
            links.append({"name": "HubCDN (10Gbps)", "url": hubcdn_url})
            
            try:
                current_url = hubcdn_url
                for _ in range(5):
                    resp = session.head(current_url, allow_redirects=False)
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get('Location')
                        if not location: break
                        
                        if "gamerxyt.com/dl.php" in location:
                            from urllib.parse import urlparse, parse_qs
                            parsed = urlparse(location)
                            query = parse_qs(parsed.query)
                            if 'link' in query:
                                google_link = query['link'][0]
                                links.append({"name": "Google Drive (Direct)", "url": google_link})
                                break
                        current_url = location
                    else:
                        break
            except Exception as e:
                print(f"Error following HubCDN redirects: {e}")

        # 3. Pixeldrain link
        pixeldrain_match = re.search(r'href="(https://pixeldrain\.(?:dev|com)/u/[^"]+)"', response_intermediate.text)
        if pixeldrain_match:
             original_link = pixeldrain_match.group(1)
             file_id = original_link.split('/')[-1]
             direct_link = f"https://pixeldrain.com/api/file/{file_id}?download"
             links.append({"name": "Pixeldrain (Direct)", "url": direct_link})

        # 4. Mega Server
        mega_match = re.search(r'href="(https://mega\.blockxpiracy\.net/[^"]+)"', response_intermediate.text)
        if mega_match:
            links.append({"name": "Mega Server", "url": mega_match.group(1)})

        # 5. Cloudflare Workers link (Generic)
        workers_match = re.search(r'href="(https://[^"]+\.workers\.dev/[^"]+)"', response_intermediate.text)
        if workers_match:
             links.append({"name": "Cloudflare Worker (Direct)", "url": workers_match.group(1)})
            
        if not links:
             return {"error": "No download links found."}
             
        return {"links": links}

    except Exception as e:
        return {"error": str(e)}

def extract_gdflix_links(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        session = requests.Session()
        session.headers.update(headers)
        
        response = session.get(url)
        response.raise_for_status()
        
        links = []
        
        # 1. Instant DL [10GBPS] (instant.busycdn.cfd)
        instant_match = re.search(r'href="(https://instant\.busycdn\.cfd/[^"]+)"', response.text)
        if instant_match:
            instant_url = instant_match.group(1)
            try:
                # Follow redirect with Referer
                # The Referer must be the GDFlix page URL
                head_headers = headers.copy()
                head_headers['Referer'] = response.url
                
                resp = session.head(instant_url, headers=head_headers, allow_redirects=True)
                final_url = resp.url
                
                # Check if it's a filesgram link with 'url' parameter
                if "filesgram" in final_url:
                    from urllib.parse import urlparse, parse_qs
                    parsed_url = urlparse(final_url)
                    query_params = parse_qs(parsed_url.query)
                    if 'url' in query_params:
                        final_url = query_params['url'][0]
                
                # Check if the result is a fastcdn-dl wrapper (can be direct or from filesgram)
                if "fastcdn-dl.pages.dev" in final_url:
                     from urllib.parse import urlparse, parse_qs
                     parsed_nested = urlparse(final_url)
                     nested_params = parse_qs(parsed_nested.query)
                     if 'url' in nested_params:
                         final_url = nested_params['url'][0]
                
                links.append({"name": "Instant DL (10Gbps)", "url": final_url})
            except Exception as e:
                print(f"Error following Instant DL redirect: {e}")
                # Fallback to original link if redirect fails
                links.append({"name": "Instant DL (10Gbps)", "url": instant_url})
            
        # 2. PixelDrain DL
        pixeldrain_match = re.search(r'href="(https://pixeldrain\.(?:dev|com)/u/[^"]+)"', response.text)
        if pixeldrain_match:
             original_link = pixeldrain_match.group(1)
             file_id = original_link.split('/')[-1]
             direct_link = f"https://pixeldrain.com/api/file/{file_id}?download"
             links.append({"name": "Pixeldrain (Direct)", "url": direct_link})
             
        if not links:
             return {"error": "No download links found on GDFlix page."}
             
        return {"links": links}
    except Exception as e:
        return {"error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Check for hubdrive.space
    if "hubdrive.space" in url:
        return jsonify({
            "error": "HubDrive.space links require interactive steps (login/captcha) and cannot be automated. "
                     "Please use the corresponding HubCloud.foo link instead, which provides the same file with direct download links."
        })
    
    if "gdflix" in url:
        result = extract_gdflix_links(url)
    else:
        result = extract_links(url)
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
