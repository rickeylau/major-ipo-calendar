#!/usr/bin/env python3
"""Select large US IPOs. Nasdaq calendar dates are not confirmed debut times."""
import argparse, hashlib, json, re, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parent
NASDAQ = 'https://api.nasdaq.com/api/ipo/calendar'
NASDAQ_PAGE = 'https://www.nasdaq.com/market-activity/ipos'
ET = ZoneInfo('America/New_York')

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def number(v):
    try:
        n = float(str(v).replace('$','').replace(',','').strip())
        return n if 0 < n < 1e15 else None
    except (ValueError, TypeError):
        return None

def day(v):
    for fmt in ('%Y-%m-%d','%m/%d/%Y'):
        try: return datetime.strptime(str(v),fmt).date().isoformat()
        except ValueError: pass
    return None

def norm(s):
    return re.sub(r'[^a-z0-9]+',' ',str(s).lower()).strip()

def eligible(name, ticker, exchange, amount, cfg, deal_type=''):
    if not re.search(r'\b(?:nasdaq|nyse)\b', str(exchange), re.I): return False
    if ticker in cfg.get('exclude_symbols',[]): return False
    if re.search(r'\b(?:acquisition corp(?:oration)?|acquisition company|blank check|spac|etf|closed end fund|investment fund)\b',norm(name)+' '+norm(deal_type)): return False
    if re.search(r'\b(?:secondary|spo|follow on|fund|spac)\b',norm(deal_type)): return False
    watched = any(re.search(r'\b'+re.escape(norm(w))+r'\b',norm(name)) for w in cfg['watch_names'] if norm(w))
    return watched or (amount is not None and amount >= cfg['min_offer_usd'])

def table_rows(data, stage):
    table = data.get(stage)
    if not isinstance(table,dict): raise ValueError('Missing Nasdaq stage: '+stage)
    if stage+'Table' in table: table=table[stage+'Table']
    if not isinstance(table,dict) or 'rows' not in table: raise ValueError('Missing Nasdaq rows: '+stage)
    rows=table['rows']
    if rows is None: return []
    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows): raise ValueError('Invalid rows: '+stage)
    return rows

def parse_nasdaq(payload,cfg):
    data=payload.get('data')
    if not isinstance(data,dict): raise ValueError('Nasdaq data missing')
    code=(payload.get('status') or {}).get('rCode')
    if code not in (None,200,'200'): raise ValueError('Nasdaq status: '+str(code))
    events=[]; withdrawn=set(); observed=set()
    for stage in ('upcoming','priced','withdrawn'):
        for row in table_rows(data,stage):
            ticker=str(row.get('proposedTickerSymbol') or '').strip().upper()
            name=str(row.get('companyName') or '').strip()
            ident=str(row.get('dealID') or ticker or norm(name))
            if not name: raise ValueError('Nasdaq row has no company name')
            if stage=='withdrawn':
                if ticker: withdrawn.add(ticker)
                continue
            d=day(row.get('expectedPriceDate' if stage=='upcoming' else 'pricedDate'))
            amount=number(row.get('dollarValueOfSharesOffered'))
            if not eligible(name,ticker,row.get('proposedExchange'),amount,cfg,row.get('dealType','')): continue
            if not d: continue
            if ticker: observed.add(ticker)
            events.append(dict(id='nasdaq-'+ident+'-pricing',symbol=ticker,name=name,date=d,kind='pricing',status='expected' if stage=='upcoming' else 'priced',offer_usd=amount,price=str(row.get('proposedSharePrice') or ''),source=NASDAQ_PAGE))
    return events,withdrawn,observed

def fetch_month(month):
    url=NASDAQ+'?'+urlencode({'date':month})
    for i in range(3):
        try:
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; MajorIPOCalendar/1.0)','Accept':'application/json'})
            with urlopen(req,timeout=20) as r: raw=r.read(8_000_001)
            if len(raw)>8_000_000: raise ValueError('Response too large')
            return json.loads(raw)
        except (OSError,ValueError) as e:
            print(f'{month} attempt {i+1}: {type(e).__name__}: {e}',flush=True)
            if i==2: raise
            time.sleep((2,5)[i])

def months(today):
    m=today.replace(day=1)
    for offset in (-1,0,1):
        k=m.year*12+m.month-1+offset
        yield f'{k//12:04d}-{k%12+1:02d}'

def combine(auto,withdrawn,cfg,today):
    start=today-timedelta(days=90); end=today+timedelta(days=90)
    by={}
    for r in auto:
        if r['symbol'] in withdrawn: continue
        k=(r['symbol'] or norm(r['name']),r['kind'])
        old=by.get(k)
        if old is None or (r['status']=='priced',r['date'])>(old['status']=='priced',old['date']): by[k]=r.copy()
    for r in cfg['manual_events']:
        if not day(r['date']) or not day(r['verified_on']) or r['kind'] not in ('pricing','listing') or r['status'] not in ('expected','priced','listed') or not r['source'].startswith('https://'): raise ValueError('Invalid manual event')
        if r['symbol'] in withdrawn: continue
        k=(r['symbol'],r['kind'])
        old=by.get(k)
        if old and old['status']=='priced': continue
        # Nasdaq expected dates are not authoritative pricing vs debut dates.
        # Prefer a separately verified issuer timetable if the provider date
        # agrees with either milestone; if it disagrees with both, do not
        # silently publish a stale issuer timetable.
        pricing=by.get((r['symbol'],'pricing'))
        related=[x['date'] for x in cfg['manual_events'] if x['symbol']==r['symbol']]
        if pricing and pricing['status']=='expected' and pricing['source']==NASDAQ_PAGE and pricing['date'] not in related:
            continue
        if r['kind']=='listing' and pricing and pricing['status']=='priced':
            manual_price=next((x['date'] for x in cfg['manual_events'] if x['symbol']==r['symbol'] and x['kind']=='pricing'),None)
            if manual_price and pricing['date']!=manual_price:
                continue
        if r['status']=='expected' and date.fromisoformat(r['date'])<today: continue
        by[k]=r.copy()
    out=[]
    for r in by.values():
        d=date.fromisoformat(r['date'])
        if start<=d<=end and not (r['status']=='expected' and d<today): out.append(r)
    return sorted(out,key=lambda r:(r['date'],r['name'],r['kind']))

def escape(s): return str(s).replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
def fold(s):
    lines=[]; buf=''
    for c in s:
        if len((buf+c).encode('utf-8'))>75: lines.append(buf);buf=' '+c
        else: buf+=c
    return '\r\n'.join(lines+[buf])

def render(events,stamp):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Major IPO Calendar//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:Major IPO Calendar']
    seen=set()
    for r in events:
        # Stable symbol+stage UID across date changes and manual/automatic sources.
        uid=hashlib.sha256((r['symbol'] or norm(r['name'])).encode()).hexdigest()[:24]+'-'+r['kind']+'@major-ipo-calendar'
        if uid in seen: raise ValueError('Duplicate UID')
        seen.add(uid); d=date.fromisoformat(r['date']); tentative=r['status']=='expected'
        label='Calendar Date' if tentative and r['source']==NASDAQ_PAGE else r['kind'].title()
        title=f"Major IPO: {r['name']} ({r['symbol'] or 'TBD'}) — {label}"+(' [Expected]' if tentative else '')
        desc=f"Status: {r['status']}. Date is subject to change. No specific trading time is asserted."
        if tentative and r['source']==NASDAQ_PAGE: desc+=' Nasdaq expected date; pricing and first trade may differ.'
        if r.get('offer_usd'): desc+=f"\nIndicative/Reported offer amount: USD {r['offer_usd']:,.0f} (provider methodology may include overallotment)."
        if r.get('price'): desc+='\nPrice: '+r['price']
        desc+='\nSource: '+r['source']+'\nVerify issuer announcement before trading.'
        lines += ['BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+stamp,f'DTSTART;VALUE=DATE:{d:%Y%m%d}',f'DTEND;VALUE=DATE:{d+timedelta(days=1):%Y%m%d}','SUMMARY:'+escape(title),'DESCRIPTION:'+escape(desc),'URL:'+r['source'],'STATUS:'+('TENTATIVE' if tentative else 'CONFIRMED'),'TRANSP:TRANSPARENT','END:VEVENT']
    return ('\r\n'.join(fold(s) for s in lines+['END:VCALENDAR'])+'\r\n').encode()

def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',action='store_true');args=p.parse_args()
    cfg=read_json(ROOT/'config.json'); now=datetime.now(timezone.utc); today=now.astimezone(ET).date()
    auto=[]; withdrawn=set()
    if not args.seed:
        for m in months(today):
            a,w,_=parse_nasdaq(fetch_month(m),cfg);auto+=a;withdrawn|=w
    rows=combine(auto,withdrawn,cfg,today)
    # Full validation occurs before replacing any output. Seed is explicitly not a live audit.
    stamp=now.strftime('%Y%m%dT%H%M%SZ'); old=ROOT/'dates.json'
    if old.exists():
        prev=read_json(old)
        if prev.get('events')==rows: stamp=prev['stamp']
    ics=render(rows,stamp)
    status={'status':'seed' if args.seed else 'ok','checked_at_utc':now.isoformat(),'source':'manual SEC filings' if args.seed else 'Nasdaq IPO calendar','event_count':len(rows),'sha256':hashlib.sha256(ics).hexdigest()}
    write(ROOT/'major-ipo.ics',ics);write(old,(json.dumps({'stamp':stamp,'events':rows},indent=2)+'\n').encode());write(ROOT/'source_status.json',(json.dumps(status,indent=2)+'\n').encode())
    print(f'{len(rows)} major IPO events; source status={status["status"]}')
if __name__=='__main__':main()
