"""seed_remaining.py — fill in documents, compliance, health, timeline, actions, regulations"""
import asyncio, asyncpg, uuid, json
from datetime import datetime, timezone, timedelta
from random import choice, randint, uniform

DSN = "postgresql://realtoros:realtoros15!@127.0.0.1:5432/realtoros"
DOC_TYPES = ['passport','contract','extract','deed','receipt','statement','report','other']

async def seed():
    conn = await asyncpg.connect(DSN)
    user_ids = [r[0] for r in await conn.fetch("SELECT id FROM users LIMIT 10")]
    client_pool = [r[0] for r in await conn.fetch("SELECT id FROM clients LIMIT 100")]
    deal_pool = [r[0] for r in await conn.fetch("SELECT id FROM deals LIMIT 30")]

    for did in deal_pool:
        for role in ['buyer','seller']:
            await conn.execute("INSERT INTO deal_participants(id,deal_id,client_id,role,created_at) VALUES($1,$2,$3,$4,now())", uuid.uuid4(), did, choice(client_pool), role)
        for dt in DOC_TYPES[:randint(2,5)]:
            cid = choice(client_pool)
            await conn.execute("INSERT INTO documents(id,deal_id,document_type,status,title,file_name,file_path,client_id,uploaded_by,created_at,updated_at) VALUES($1,$2,$3,'received',$4,$5,$6,$7,$8,now(),now())",
                uuid.uuid4(), did, dt, f"{dt}.pdf", f"{dt}_{did.hex[:8]}.pdf", f"/docs/{did.hex[:8]}/{dt}.pdf", cid, choice(user_ids))
        score = round(uniform(50,100),2)
        await conn.execute("INSERT INTO compliance_audits(id,deal_id,correlation_id,audit_type,score,result,risk_level,blocking_issues,used_regulations,created_at) VALUES($1,$2,$3,'deal_check',$4,'{}'::jsonb,$5,'[]'::jsonb,$6,now())",
            uuid.uuid4(), did, str(uuid.uuid4()), score, "low" if score>80 else "medium" if score>60 else "high", json.dumps(choice([["218-fz"],["102-fz","218-fz"],["tax-code","218-fz","102-fz"]])))
        await conn.execute("INSERT INTO deal_health_snapshots(id,deal_id,score,compliance_score,risk_score,sla_score,document_score,activity_score,calculated_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,now())",
            uuid.uuid4(), did, round(uniform(40,100),1), round(uniform(50,100),1), round(uniform(0,50),1), round(uniform(40,100),1), round(uniform(30,100),1), round(uniform(40,100),1))
        for _ in range(randint(3,8)):
            await conn.execute("INSERT INTO deal_timeline_events(id,deal_id,event_type,source_component,title,description,created_at) VALUES($1,$2,$3,$4,$5,$6,$7)",
                uuid.uuid4(), did, choice(["stage_changed","document_uploaded","compliance_check","risk_detected"]),
                choice(["workflow","documents","compliance","risks","agent"]), choice(["Deal created","Document uploaded","Compliance check passed","Risk assessed"]),
                "Seed event", datetime.now(timezone.utc)-timedelta(days=randint(1,60)))

    for did in deal_pool[:10]:
        await conn.execute("INSERT INTO deal_actions(id,deal_id,action_type,title,description,priority,status,created_at) VALUES($1,$2,'task',$3,$4,$5,'pending',now())",
            uuid.uuid4(), did, choice(["Upload missing document","Verify EGRN","Check mortgage approval","Notify client"]), "Auto-generated", choice(["critical","high","medium","low"]))
    await conn.close()
    print(f"Done: documents, compliance, health, timeline, actions")

asyncio.run(seed())
