import unittest, json
from datetime import date
from pathlib import Path
from unittest.mock import patch
import major_ipo as m
CFG=json.loads((Path(__file__).parent/'config.json').read_text())
TODAY=date(2026,11,16)
def row(name='Large Co',ticker='LARGE',amount='$2,000,000,000',d='11/19/2026',**kw):
    return dict(proposedTickerSymbol=ticker,companyName=name,proposedExchange='NASDAQ Global',dollarValueOfSharesOffered=amount,expectedPriceDate=d,dealID=ticker,**kw)
def payload(up=(),priced=(),withdrawn=()):
    return {'status':{'rCode':200},'data':{'upcoming':{'upcomingTable':{'rows':list(up)}},'priced':{'rows':list(priced)},'withdrawn':{'rows':list(withdrawn)}}}
class TestIPO(unittest.TestCase):
    def test_threshold(self):
        a,_,_=m.parse_nasdaq(payload([row(),row(ticker='S',amount='$100,000')]),CFG);self.assertEqual(len(a),1)
    def test_watch(self):
        a,_,_=m.parse_nasdaq(payload([row('OpenAI','OAI',None)]),CFG);self.assertEqual(len(a),1)
    def test_spac(self):
        a,_,_=m.parse_nasdaq(payload([row('Example Acquisition Corp.','SPAC')]),CFG);self.assertFalse(a)
    def test_secondary(self):
        a,_,_=m.parse_nasdaq(payload([row(dealType='Secondary')]),CFG);self.assertFalse(a)
    def test_blank_date(self):
        a,_,_=m.parse_nasdaq(payload([row(d='')]),CFG);self.assertFalse(a)
    def test_schema(self):
        with self.assertRaises(ValueError):m.parse_nasdaq({'data':{}},CFG)
    def test_empty(self):
        a,w,_=m.parse_nasdaq(payload(),CFG);self.assertEqual((a,w),([],set()));self.assertNotIn(b'VEVENT',m.render([], '20261116T010000Z'))
    def test_seed(self):
        a=m.combine([],set(),CFG,TODAY);self.assertEqual([x['date'] for x in a],['2026-11-18','2026-11-19'])
    def test_withdrawal(self):
        self.assertFalse(m.combine([],{'ANT'},CFG,TODAY))
    def test_nasdaq_expected_listing_matches_seed(self):
        a,w,_=m.parse_nasdaq(payload([row('Anthropic','ANT')]),CFG);b=m.combine(a,w,CFG,TODAY);self.assertEqual([x['date'] for x in b],['2026-11-18','2026-11-19'])
    def test_date_conflict(self):
        a,w,_=m.parse_nasdaq(payload([row('Anthropic','ANT',d='11/25/2026')]),CFG);b=m.combine(a,w,CFG,TODAY);self.assertEqual([x['date'] for x in b],['2026-11-25'])
    def test_changed_pricing_hides_stale_listing(self):
        r=row('Anthropic','ANT');r['pricedDate']='11/20/2026'
        a,w,_=m.parse_nasdaq(payload(priced=[r]),CFG)
        b=m.combine(a,w,CFG,TODAY)
        self.assertEqual([(x['date'],x['kind']) for x in b],[('2026-11-20','pricing')])
    def test_past_expected_removed(self):
        self.assertFalse(m.combine([],set(),CFG,date(2026,11,20)))
    def test_render(self):
        b=m.render(m.combine([],set(),CFG,TODAY),'20261116T010000Z');self.assertEqual(b.count(b'BEGIN:VEVENT'),2);self.assertEqual(b.count(b'STATUS:TENTATIVE'),2);self.assertIn(b'DTSTART;VALUE=DATE:20261119',b)
    def test_months(self): self.assertEqual(list(m.months(date(2026,12,1))),['2026-11','2026-12','2027-01'])
    def test_issuer_url(self): self.assertTrue(all('sec.gov' in x['source'] for x in m.combine([],set(),CFG,TODAY)))
if __name__=='__main__':unittest.main()
