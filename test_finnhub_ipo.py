import io, json, os, unittest
from datetime import date
from urllib.error import HTTPError
from unittest.mock import patch, MagicMock
from pathlib import Path
import major_ipo as m
CFG=json.loads((Path(__file__).parent/'config.json').read_text())
TODAY=date(2026,11,16)
def row(**kwargs):
    return dict(dict(name='Large Co',symbol='LARGE',exchange='NASDAQ',date='2026-11-19',status='expected',totalSharesValue=2_000_000_000,price='70-78'),**kwargs)
def parse(*rows): return m.parse_finnhub({'ipoCalendar':list(rows)}, CFG)
class TestFinnhub(unittest.TestCase):
    def test_amount(self): self.assertEqual(len(parse(row(),row(symbol='SMALL',totalSharesValue=2))[0]),1)
    def test_watch(self): self.assertEqual(len(parse(row(name='OpenAI',totalSharesValue=None))[0]),1)
    def test_spac(self): self.assertFalse(parse(row(name='ABC Acquisition Corp'))[0])
    def test_filed(self): self.assertFalse(parse(row(status='filed'))[0])
    def test_withdrawn(self): self.assertEqual(parse(row(symbol='ANT',status='withdrawn'))[1],{'ANT'})
    def test_empty(self): self.assertEqual(parse(),([],set()))
    def test_schema(self):
        for payload in ({'error':'invalid key'},{'ipoCalendar':None}):
            with self.assertRaises(ValueError): m.parse_finnhub(payload,CFG)
    def test_status(self):
        with self.assertRaises(ValueError): parse(row(status='unknown'))
    def test_expected_label(self):
        b=m.render(parse(row())[0],'20261116T010000Z');self.assertIn(b'Calendar Date [Expected]',b);self.assertIn(b'STATUS:TENTATIVE',b)
    def test_priced_label(self):
        b=m.render(parse(row(status='priced'))[0],'20261116T010000Z');self.assertIn(b'Calendar Date [Priced',b);self.assertIn(b'STATUS:TENTATIVE',b)
    def test_issuer_dates(self):
        a,w=parse(row(name='Anthropic',symbol='ANT'));b=m.combine(a,w,CFG,TODAY);self.assertEqual([x['date'] for x in b],['2026-11-18','2026-11-19'])
    def test_conflict(self):
        a,w=parse(row(name='Anthropic',symbol='ANT',date='2026-11-25'));b=m.combine(a,w,CFG,TODAY);self.assertEqual([x['date'] for x in b],['2026-11-25'])
    def test_auth_header_and_range(self):
        fake=MagicMock();fake.open.return_value.__enter__.return_value.read.return_value=b'{"ipoCalendar":[]}'
        with patch.object(m,'build_opener',return_value=fake):
            self.assertEqual(m.fetch_finnhub('2028-02','TEST_SECRET'),{'ipoCalendar':[]})
        req=fake.open.call_args.args[0];self.assertIn('to=2028-02-29',req.full_url);self.assertNotIn('TEST_SECRET',req.full_url);self.assertEqual(req.get_header('X-finnhub-token'),'TEST_SECRET')
    def test_auth_failure(self):
        fake=MagicMock();fake.open.side_effect=HTTPError('https://finnhub.io',403,'Forbidden',{},io.BytesIO())
        with patch.object(m,'build_opener',return_value=fake),patch.object(m.time,'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError,'HTTP 403'):m.fetch_finnhub('2026-11','TEST_SECRET')
            self.assertEqual(fake.open.call_count,1);sleep.assert_not_called()
    def test_timeout_retry(self):
        fake=MagicMock();resp=MagicMock();resp.__enter__.return_value.read.return_value=b'{"ipoCalendar":[]}'
        fake.open.side_effect=[TimeoutError(),resp]
        with patch.object(m,'build_opener',return_value=fake),patch.object(m.time,'sleep'):
            self.assertEqual(m.fetch_finnhub('2026-11','TEST_SECRET'),{'ipoCalendar':[]})
        self.assertEqual(fake.open.call_count,2)
    def test_missing_secret(self):
        with patch.dict(os.environ,{'FINNHUB_API_KEY':''}),patch('sys.argv',['major_ipo.py']):
            with self.assertRaisesRegex(RuntimeError,'Missing FINNHUB_API_KEY'):m.main()
