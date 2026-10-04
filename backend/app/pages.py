"""Static site pages rendered in one shared template. No scripts and no inline handlers (compatible with the site's CSP). English only for now."""
from html import escape

NAV = [("/", "Check a message"), ("/about", "How it works"), ("/resources", "Help & FAQ"), ("/privacy", "Privacy"), ("/terms", "Terms")]
CSS = ("body{margin:0;background:#06101d;color:#eaf2fb;font:18px/1.6 system-ui,'Segoe UI','Noto Sans Devanagari','Noto Sans Tamil',Roboto,sans-serif}a{color:#2ee6c5}"
       "header,footer,main{max-width:820px;margin:0 auto;padding:16px 18px}header{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;justify-content:space-between;border-bottom:1px solid #26384d}"
       "header b{font-size:20px}nav a{margin-right:14px;text-decoration:none;color:#a9bbcf}nav a[aria-current]{color:#fff;border-bottom:2px solid #2ee6c5}"
       "h1{font-size:clamp(30px,6vw,44px);line-height:1.1}h2{margin-top:30px}details{border:1px solid #26384d;border-radius:12px;padding:10px 14px;margin:10px 0;background:#0c1a2c}"
       "summary{cursor:pointer;font-weight:600}footer{color:#a9bbcf;font-size:15px;border-top:1px solid #26384d;margin-top:30px}"
       ".skip{position:absolute;left:-999px;top:8px;background:#fff;color:#000;padding:8px 12px;border-radius:8px}.skip:focus{left:8px}"
       "a:focus-visible,summary:focus-visible{outline:3px solid #7db3ff;outline-offset:2px}@media print{body{background:#fff;color:#000}nav{display:none}}")

PAGES = {
 "about": ("How it works", "How ScamShield Bharat checks suspicious investment messages, screenshots and links, and what it will never do.", """
<h1>How ScamShield Bharat works</h1>
<p>Paste a suspicious investment message, upload a screenshot, check a link or speak it. ScamShield points out the warning signs it can see, quotes the exact words, explains why they matter and suggests safe next steps. <b>Detect, explain, verify, protect.</b></p>
<h2>What it looks for</h2>
<ul><li>Guaranteed or unrealistically high returns</li><li>Pressure to act fast, and scarcity or "VIP" tactics</li><li>Requests for OTPs, PINs or passwords</li><li>Requests to pay money first, or claims to speak for an official body</li><li>Threats such as account closure</li><li>Links that imitate an official site, hide their destination or look unusual</li><li>Wording that matches scam reports shared by other users (see below)</li></ul>
<h2>What it will never do</h2>
<p>It does not give stock tips, say what to buy, sell or hold, predict prices or returns, recommend brokers or products, or ask for your OTP, PIN or password. A result is a set of warning signs to verify, not a verdict.</p>
<h2>How it learns</h2>
<p>Only if you choose to. After a result you can agree to share short masked word fragments (no digits, links or IDs) and say whether it was a scam. Recurring phrases are reviewed by a person before they affect any result. You can delete what you shared.</p>
<h2>Languages</h2>
<p>Reports are available in English, हिन्दी and தமிழ். These information pages are in English for now.</p>
<p><a href="/">Check a message now</a></p>"""),
 "privacy": ("Privacy", "What ScamShield Bharat processes, what it stores, and the controls you have.", """
<h1>Privacy</h1>
<p>Short version: your message is analysed and not kept, unless you choose to share masked fragments to help the system learn.</p>
<h2>What happens to what you submit</h2>
<p>Text, screenshots and links are processed in memory to produce your report. Screenshots are read for text and then discarded. Links are examined as text only; ScamShield does not open them.</p>
<h2>What is stored</h2>
<ul><li><b>On the server, about your checks:</b> nothing, except anonymous counters (how many checks, which warning types).</li>
<li><b>If you opt in:</b> short masked 2 to 3 word fragments and your label (scam, not a scam, not sure). The full message is not stored. They are deleted after 90 days, or sooner if you press Delete.</li>
<li><b>In your browser only:</b> a list of recent results (state and warning types, no message text) and your practice progress. "Delete all history" clears it.</li></ul>
<h2>Cookies, tracking and ads</h2><p>No cookies, no analytics, no advertising and no third-party scripts.</p>
<h2>Voice input</h2>
<p>If you use the microphone, your browser's speech service turns speech into text. In Chrome and Edge this sends audio to the browser maker's servers. ScamShield only receives the resulting text. Do not speak OTPs, passwords or PINs.</p>
<h2>Optional AI explanation</h2>
<p>Off by default and available only if this deployment has it configured. If you tick the box, the text of that check is sent, with numbers and IDs masked, to the AI provider the deployment uses.</p>
<h2>Please never enter</h2><p>OTPs, passwords, PINs, card numbers or bank logins. ScamShield will never ask for them.</p>
<h2>Questions</h2>
<p>This is a prototype without accounts. Use the Delete buttons to remove what you shared. For anything else, contact the team that runs this deployment.</p>"""),
 "terms": ("Terms of use", "Terms for using the ScamShield Bharat prototype.", """
<h1>Terms of use</h1>
<p>ScamShield Bharat is a prototype built for the SANGYAN hackathon. By using it you agree to the following.</p>
<h2>Not advice</h2>
<p>It is not investment, legal or financial advice, and it is not a regulator. Results are warning signs based only on what you provide. A low-risk result does not mean something is genuine; a high-risk result does not prove fraud.</p>
<h2>Your responsibility</h2><p>Verify organisations and senders through official sources before acting. Do not send money or codes because of a message.</p>
<h2>Acceptable use</h2>
<p>Do not submit other people's private information, unlawful content or anything you have no right to share. Do not try to disrupt the service or to poison the learning feature with false reports.</p>
<h2>No warranty</h2>
<p>The service is provided as is, without any promise of accuracy or availability. To the extent the law allows, the team is not liable for decisions made using it.</p>
<h2>Changes</h2><p>These terms may change as the prototype evolves.</p>"""),
 "resources": ("Help & FAQ", "What to do if you think you were scammed, official places to verify and report, and common questions.", """
<h1>Help and FAQ</h1>
<h2>If you think you have been scammed</h2>
<ol><li>Stop sending money and do not share any more codes.</li><li>Call your bank right away and ask them to block the transaction or card.</li>
<li>Report it quickly on the National Cyber Crime Reporting Portal, or call the helpline <b>1930</b>.</li><li>Keep screenshots, numbers, links and payment receipts.</li></ol>
<h2>Official places to verify and report</h2>
<ul><li><a href="https://cybercrime.gov.in" rel="noopener noreferrer">National Cyber Crime Reporting Portal</a> (helpline 1930)</li>
<li><a href="https://scores.sebi.gov.in" rel="noopener noreferrer">SEBI SCORES</a> for complaints against SEBI-regulated entities</li>
<li><a href="https://www.sebi.gov.in" rel="noopener noreferrer">SEBI</a> to check whether an adviser, broker or intermediary is registered</li>
<li><a href="https://nsdl.co.in" rel="noopener noreferrer">NSDL</a> for depository information</li></ul>
<p>We link to official sites but do not control them. Type addresses yourself rather than tapping links in messages, and confirm details on the official site.</p>
<h2>Frequently asked questions</h2>
<details><summary>Does ScamShield tell me what to invest in?</summary><p>No. It never recommends buying, selling or holding anything and never predicts returns.</p></details>
<details><summary>Is my message saved?</summary><p>No, unless you tick the box to share masked fragments after a result. See the <a href="/privacy">privacy page</a>.</p></details>
<details><summary>Why did it flag a message that looks normal?</summary><p>It reacts to wording such as guaranteed returns, urgency, or requests for codes and money. Some genuine messages use similar words. Treat a flag as a reason to verify, not as proof.</p></details>
<details><summary>It found nothing. Is the message safe?</summary><p>Not necessarily. ScamShield can miss new or reworded scams. Verify through an official source before you act.</p></details>
<details><summary>Which languages work?</summary><p>Reports come in English, Hindi and Tamil. Screenshots are read in the languages installed on the server.</p></details>"""),
 "offline": ("Offline", "ScamShield Bharat is offline.", """
<h1>You are offline</h1>
<p>ScamShield needs a connection to analyse a message. Reconnect and try again. Until then, remember: never share an OTP, and do not send money because of a message.</p>
<p><a href="/">Try again</a></p>"""),
 "404": ("Page not found", "This page does not exist.", """
<h1>Page not found</h1><p>That page does not exist.</p><p><a href="/">Check a message</a> · <a href="/resources">Help and FAQ</a></p>"""),
}


def render(slug):
    title, desc, body = PAGES[slug]
    nav = "".join(f'<a href="{h}"' + (' aria-current="page"' if h == "/" + slug else "") + f">{t}</a>" for h, t in NAV)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)} - ScamShield Bharat</title><meta name="description" content="{escape(desc)}"><meta name="theme-color" content="#06101d">'
            f'<meta property="og:title" content="{escape(title)} - ScamShield Bharat"><meta property="og:description" content="{escape(desc)}"><meta property="og:type" content="website">'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="manifest" href="/manifest.webmanifest"><style>{CSS}</style></head><body>'
            f'<a class="skip" href="#main">Skip to main content</a><header><b>ScamShield Bharat</b><nav aria-label="Site">{nav}</nav></header><main id="main">{body}</main>'
            f'<footer>ScamShield Bharat identifies potential warning signs. It does not provide investment advice or guarantee that content is legitimate or fraudulent. '
            f'<a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></footer></body></html>')
