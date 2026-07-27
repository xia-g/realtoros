import asyncio
import asyncpg

async def clean():
    conn = await asyncpg.connect(
        host='127.0.0.1', port=5432, user='realtoros',
        password='realtoros15pass', database='realtoros'
    )
    tables = ['graph_edges','graph_nodes','document_chunks','embeddings',
              'deal_participants','resolution_attempt','deals','documents',
              'properties','consumer_processed_events','event_outbox']
    for t in tables:
        try:
            await conn.execute(f'DELETE FROM {t}')
        except Exception as e:
            print(f'  SKIP {t}: {e}')
    await conn.execute("DELETE FROM clients WHERE inn IS DISTINCT FROM '780527855675' OR inn IS NULL")
    await conn.close()
    print('DB cleaned')

asyncio.run(clean())
