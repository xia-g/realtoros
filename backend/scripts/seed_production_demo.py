"""seed_production_demo.py — fully idempotent seed."""
import asyncio, hashlib, json, os, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from random import choice, randint, uniform, seed as set_seed
set_seed(42)
DSN = os.getenv("DATABASE_URL","postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros").replace("+asyncpg","")
FIRST_NAMES = ["Иван","Александр","Сергей","Андрей","Дмитрий","Максим","Евгений","Владимир","Михаил","Алексей",
               "Ольга","Елена","Наталья","Анна","Мария","Светлана","Екатерина","Татьяна","Ирина","Юлия"]
LAST_NAMES = ["Иванов","Петров","Сидоров","Кузнецов","Попов","Смирнов","Волков","Фёдоров","Морозов","Новиков"]
STAGES = ["initiated","verification","mortgage","registration","closing"]
DOC_TYPES = ["passport","egrn","purchase_agreement","mortgage_contract","insurance","consent_spouse","valuation_report"]

async def seed():
    import asyncpg
    conn = await asyncpg.connect(DSN)
    try:
        # Check deals count for idempotency
        if await conn.fetchval("SELECT count(*) FROM deals") and await conn.fetchval("SELECT count(*) FROM clients"):
            print(f"Seed data exists. Skipping.")
            return

        # Roles
        role_ids = [r["id"] for r in await conn.fetch("SELECT id FROM roles ORDER BY name LIMIT 8")]
        if not role_ids:
            for name in ["admin","executive","broker","realtor","lawyer","compliance","accountant","viewer"]:
                rid = uuid.uuid4()
                await conn.execute("INSERT INTO roles(id,name,permissions,is_system,created_at,updated_at) VALUES($1,$2,'{}'::jsonb,true,now(),now())", rid, name)
                role_ids.append(rid)
        print(f"Roles: {len(role_ids)}")

        # Users
        user_ids = [r["id"] for r in await conn.fetch("SELECT id FROM users LIMIT 10")]
        if not user_ids:
            for i in range(6):
                uid = uuid.uuid4()
                await conn.execute("INSERT INTO users(id,role_id,status,full_name,phone,email,password_hash,created_at,updated_at) VALUES($1,$2,'active',$3,$4,$5,$6,now(),now())",
                    uid, role_ids[i%len(role_ids)], f"{FIRST_NAMES[i]} {LAST_NAMES[i]}",
                    f"+7900{100000+i:07d}", f"user{i}@realtor.ru", hashlib.sha256(b"password123").hexdigest())
                user_ids.append(uid)
        print(f"Users: {len(user_ids)}")

        # Clients
        client_pool = [r["id"] for r in await conn.fetch("SELECT id FROM clients LIMIT 100")]
        if not client_pool:
            for i in range(100):
                cid = uuid.uuid4()
                await conn.execute("INSERT INTO clients(id,full_name,phone,email,status,source,created_by,created_at,updated_at) VALUES($1,$2,$3,$4,'active',$5,$6,now(),now())",
                    cid, f"{choice(FIRST_NAMES)} {choice(LAST_NAMES)}", f"+7901{i:08d}", f"client{i}@mail.ru",
                    choice(["referral","site","telegram","call","other"]), choice(user_ids))
                client_pool.append(cid)
        print(f"Clients: {len(client_pool)}")

        # Properties
        prop_pool = [r["id"] for r in await conn.fetch("SELECT id FROM properties LIMIT 50")]
        if not prop_pool:
            for i in range(50):
                pid = uuid.uuid4()
                await conn.execute(
                    "INSERT INTO properties(id,property_type,status,deal_type,title,address,area_total,rooms,price,price_currency,price_per_meter,owner_id,created_by,created_at,updated_at) "
                    "VALUES($1,$2,'available',$3,$4,$5,$6,$7,$8,'RUB',$9,$10,$11,now(),now())",
                    pid, choice(["apartment","house","commercial","land","townhouse"]), choice(["sale","rent_short","rent_long","commercial"]),
                    f"Object #{i+1}", f"ул.{choice(['Ленина','Пушкина','Советская','Мира'])} д.{randint(1,100)}",
                    round(uniform(25,200),2), randint(1,5), randint(3000000,25000000),
                    round(randint(3000000,25000000)/uniform(25,200),2), choice(client_pool), choice(user_ids))
                prop_pool.append(pid)
        print(f"Properties: {len(prop_pool)}")

        # Deals
        deal_pool = [r["id"] for r in await conn.fetch("SELECT id FROM deals LIMIT 30")]
        if not deal_pool:
            for i in range(30):
                did = uuid.uuid4()
                await conn.execute("INSERT INTO deals(id,deal_type,status,property_id,title,price,price_currency,start_date,created_by,created_at,updated_at) VALUES($1,$2,'initiated',$3,$4,$5,'RUB',now(),$6,now(),now())",
                    did, choice(["sale","rent_short","rent_long","mortgage","commercial"]),
                    choice(prop_pool), f"Deal #{i+1}", randint(3000000,20000000), choice(user_ids))
                deal_pool.append(did)
            # Participants + Documents
            for did in deal_pool:
                for role in ["buyer","seller"]:
                    await conn.execute("INSERT INTO deal_participants(id,deal_id,client_id,role,created_at) VALUES($1,$2,$3,$4,now())", uuid.uuid4(), did, choice(client_pool), role)
                for dt in DOC_TYPES[:randint(2,5)]:
                    await conn.execute("INSERT INTO documents(id,deal_id,document_type,status,title,file_name,file_path,uploaded_by,created_at,updated_at) VALUES($1,$2,$3,'uploaded',$4,$5,$6,$7,now(),now())",
                        uuid.uuid4(), did, dt, f"{dt}.pdf", f"{dt}_{did.hex[:8]}.pdf", f"/docs/{did.hex[:8]}/{dt}.pdf", choice(user_ids))
            # Compliance + Health + Timeline
            for did in deal_pool:
                score = round(uniform(50,100),2)
                await conn.execute("INSERT INTO compliance_audits(id,deal_id,correlation_id,audit_type,score,result,risk_level,blocking_issues,used_regulations,created_at) VALUES($1,$2,$3,'deal_check',$4,'{}'::jsonb,$5,'[]'::jsonb,$6,now())",
                    uuid.uuid4(), did, str(uuid.uuid4()), score, "low" if score>80 else "medium" if score>60 else "high", json.dumps([["218-fz"],["102-fz","218-fz"],["tax-code","218-fz","102-fz"]][randint(0,2)]))
                await conn.execute("INSERT INTO deal_health_snapshots(id,deal_id,score,compliance_score,risk_score,sla_score,document_score,activity_score,calculated_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,now())",
                    uuid.uuid4(), did, round(uniform(40,100),1), round(uniform(50,100),1), round(uniform(0,50),1), round(uniform(40,100),1), round(uniform(30,100),1), round(uniform(40,100),1))
                for _ in range(randint(3,8)):
                    await conn.execute("INSERT INTO deal_timeline_events(id,deal_id,event_type,source_component,title,description,created_at) VALUES($1,$2,$3,$4,$5,$6,$7)",
                        uuid.uuid4(), did, choice(["stage_changed","document_uploaded","compliance_check","risk_detected"]),
                        choice(["workflow","documents","compliance","risks","agent"]), choice(["Deal created","Document uploaded","Compliance check passed","Risk assessed"]),
                        "Seed event", datetime.now(timezone.utc)-timedelta(days=randint(1,60)))
            # Actions + Regulations
            for did in deal_pool[:10]:
                await conn.execute("INSERT INTO deal_actions(id,deal_id,action_type,title,description,priority,status,created_at) VALUES($1,$2,'task',$3,$4,$5,'pending',now())",
                    uuid.uuid4(), did, choice(["Upload missing document","Verify EGRN","Check mortgage approval","Notify client"]), "Auto-generated", choice(["critical","high","medium","low"]))
            for code, name in [("218-fz","ФЗ-218 О регистрации"),("102-fz","ФЗ-102 Об ипотеке"),("tax-code","Налоговый кодекс РФ"),("214-fz","ФЗ-214 О долевом строительстве")]:
                await conn.execute("INSERT INTO regulations(id,code,name,status,created_at,updated_at) VALUES($1,$2,$3,'active',now(),now())", uuid.uuid4(), code, name)
        print(f"Deals: {len(deal_pool)} | Docs: ~{len(deal_pool)*3} | Regs: 4")

        print(f"\n=== SEED COMPLETE ===")
        print(f"Clients: {len(client_pool)} | Properties: {len(prop_pool)} | Deals: {len(deal_pool)}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())
