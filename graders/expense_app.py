"""Hidden black-box oracle: no imports from the implementation or reference."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest


class Grade(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"expenses.json"
        self.app=Path(os.environ.get("SUBMISSION_ROOT","/submission"))/"expense_app"/"ledger.py"

    def call(self,*args,valid=True,db=None):
        path=db or self.db
        before=path.read_bytes() if path.exists() else None
        result=subprocess.run([sys.executable,str(self.app),"--db",str(path),*args],
            capture_output=True,text=True,timeout=2,cwd=self.temp.name)
        if valid:
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode,0,"invalid operation succeeded")
        self.assertTrue(result.stderr.strip(),"missing diagnostic")
        self.assertEqual(path.read_bytes() if path.exists() else None,before,"invalid operation changed storage")

    def add(self,amount="12.34",category="food",date="2024-02-29",**kw):
        return self.call("add","--amount",amount,"--category",category,"--date",date,**kw)

    def test_core_and_persistence(self):
        a=self.add(category=" food ")
        self.assertEqual(a,dict(id=1,amount_cents=1234,category="food",date="2024-02-29"))
        b=self.add("0.66","travel","2000-01-01")
        self.assertEqual(b["id"],2)
        self.assertEqual(self.call("list"),[a,b])
        self.assertEqual(self.call("list","--category"," food "),[a])
        self.assertEqual(self.call("list","--category","missing"),[])
        self.assertEqual(self.call("summary"),dict(count=2,total_cents=1300,by_category={"food":1234,"travel":66}))
        self.assertEqual(json.loads(self.db.read_text()),dict(next_id=3,expenses=[a,b]))
        before=self.db.read_bytes()
        self.call("list");self.call("summary")
        self.assertEqual(self.db.read_bytes(),before)

    def test_empty_and_separate_databases(self):
        self.assertEqual(self.call("list"),[])
        self.assertEqual(self.call("summary"),dict(count=0,total_cents=0,by_category={}))
        self.assertFalse(self.db.exists())
        self.add()
        other=Path(self.temp.name)/"other.json"
        self.assertEqual(self.call("list",db=other),[])
        self.assertEqual(self.add(db=other)["id"],1)
        self.assertEqual(len(self.call("list")),1)

    def test_invalid_amounts_do_not_consume_ids(self):
        for amount in ("0","0.00","-1","+1","1e2","NaN","Infinity","1.001"," 1","1 ",".5","1.","1000000.01","１","", "1_000"):
            with self.subTest(amount=amount): self.add(amount,valid=False)
        self.assertEqual(self.add()["id"],1)
        self.add("bad",valid=False)
        self.assertEqual(self.add()["id"],2)

    def test_invalid_dates_categories_and_commands(self):
        self.add()
        for date in ("2023-02-29","1900-02-29","2024-04-31","2024-1-01","0000-01-01","2024-01-01Z","2024-01-01 "):
            with self.subTest(date=date): self.add(date=date,valid=False)
        for category in ("", "  ","x"*41):
            with self.subTest(category=category):
                self.add(category=category,valid=False)
                self.call("list","--category",category,valid=False)
        self.call("unknown",valid=False)
        self.call("add","--amount","2",valid=False)

    def test_boundaries_unicode_and_exact_cents(self):
        rows=[]
        for amount,cents,category,date in (("0.01",1,"café ☕","0001-01-01"),
                ("1000000.00",100000000,"x"*40,"9999-12-31"),
                ("0001.2",120,"Food","2000-02-29"),("0.29",29,"food","2024-02-29")):
            row=self.add(amount,category,date)
            self.assertEqual(row,dict(id=len(rows)+1,amount_cents=cents,category=category,date=date))
            rows.append(row)
        self.assertEqual(self.call("list"),rows)
        self.assertEqual(self.call("summary"),dict(count=4,total_cents=100000150,
            by_category={"café ☕":1,"x"*40:100000000,"Food":120,"food":29}))

    def test_deterministic_sequence(self):
        rng=random.Random(87123);rows=[];totals={}
        for i in range(15):
            n=rng.randint(1,999999);category=rng.choice(["a","B","café"])
            row=dict(id=i+1,amount_cents=n,category=category,date="2024-06-30")
            self.assertEqual(self.add(f"{n//100}.{n%100:02d}",category,"2024-06-30"),row)
            rows.append(row);totals[category]=totals.get(category,0)+n
        self.assertEqual(self.call("list"),rows)
        self.assertEqual(self.call("summary"),dict(count=15,total_cents=sum(totals.values()),by_category=totals))

    def test_corrupt_storage_never_reset(self):
        row=dict(id=1,amount_cents=1,category="x",date="2024-01-01")
        invalid=["", "{", "[]", "null", json.dumps(dict(next_id=1,expenses=[],extra=1)),
            json.dumps(dict(next_id=True,expenses=[])),json.dumps(dict(next_id=5,expenses=[]))]
        for field,value in (("id",True),("id",2),("amount_cents",True),("amount_cents",0),
                ("category"," x "),("date","2023-02-29")):
            invalid.append(json.dumps(dict(next_id=2,expenses=[dict(row,**{field:value})])))
        for data in invalid:
            with self.subTest(storage=data):
                self.db.write_text(data)
                self.call("list",valid=False);self.call("summary",valid=False);self.add(valid=False)
