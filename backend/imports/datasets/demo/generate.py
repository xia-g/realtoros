"""Generate demo dataset: 1000 bank rows, 300 documents, 3 tax periods."""
import csv, hashlib, json, os, random, uuid
from datetime import date, timedelta

BASE = os.path.dirname(__file__)
random.seed(42)

companies = ["00000000-0000-0000-0000-000000000001"]
counterparties = ["ООО Ромашка", "ИП Иванов", "АО Бета", "ПАО Гамма", "ООО Дельта", "ИП Петров", "ЗАО Сигма", "ООР Омега"]
descriptions = ["Оплата по договору", "Аренда помещения", "Закупка материалов", "Услуги связи",
                "Командировочные расходы", "Налоговый платёж", "Заработная плата", "Возврат поставщику"]
accounts = ["40702810", "40702810", "40702810", "40802810"]

# 1000 bank rows (CSV)
rows = []
for i in range(1000):
    amt = round(random.uniform(100, 500000), 2)
    d = date(2026, 1, 1) + timedelta(days=random.randint(0, 364))
    rows.append({
        "id": str(uuid.uuid4()),
        "date": d.isoformat(),
        "amount": str(amt if random.random() > 0.4 else -amt),
        "currency": "RUB",
        "counterparty": random.choice(counterparties),
        "description": random.choice(descriptions),
        "account": random.choice(accounts),
    })

with open(os.path.join(BASE, "bank_export.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id","date","amount","currency","counterparty","description","account"])
    w.writeheader(); w.writerows(rows)
print(f"Generated {len(rows)} bank rows → bank_export.csv")

# 300 document filenames
doc_names = []
for i in range(300):
    t = random.choice(["invoice","receipt","contract","act","payment_order","other"])
    names = {"invoice": ["invoice_","счет_","bill_"], "receipt": ["receipt_","чек_"], "contract": ["contract_","договор_"],
             "act": ["act_","акт_"], "payment_order": ["payment_","платеж_"], "other": ["doc_","документ_"]}
    prefix = random.choice(names[t])
    doc_names.append(f"{prefix}{i+1}.pdf")

meta = [{"filename": n, "classification": n.split("_")[0]} for n in doc_names]
with open(os.path.join(BASE, "documents_manifest.json"), "w") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
print(f"Generated {len(doc_names)} document references → documents_manifest.json")
print("Demo dataset ready")
