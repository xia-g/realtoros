'use client'
import { useState } from 'react'; import { Sidebar } from '@/components/layout/sidebar'
export default function OCRPage() {
  const [text, setText] = useState(''); const [result, setResult] = useState<any>(null)
  const classify = async ()=>{
    try {
      const r = await fetch('http://localhost:8000/classify', { method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text: text||'test', filename:'doc.pdf'}) })
      setResult(await r.json())
    } catch(e:any) { setResult({error:e.message}) }
  }
  return (<div className="flex h-screen"><Sidebar /><main className="flex-1 p-6 overflow-auto">
    <h1 className="text-2xl font-bold mb-6">OCR классификация</h1>
    <div className="grid grid-cols-2 gap-4 mb-6">
      {['invoice','receipt','contract','act','payment_order','other'].map(c=>(<div key={c} className="p-4 bg-white rounded-xl border"><p className="text-lg font-bold text-center">{c}</p></div>))}
    </div>
    <div className="bg-white rounded-xl border p-6">
      <textarea value={text} onChange={e=>setText(e.target.value)} rows={4} className="w-full border rounded-lg p-2 text-sm mb-4" placeholder="OCR text or filename..." />
      <button onClick={classify} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">Классифицировать</button>
    </div>
    {result && <div className="bg-white rounded-xl border p-6 mt-4"><pre className="text-xs">{JSON.stringify(result,null,2)}</pre></div>}
  </main></div>)
}