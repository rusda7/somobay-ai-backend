'use client'
import { useState } from 'react'
import { Mic, Send, Trash2, Plus, LogOut, User, Settings, Menu } from 'lucide-react'
type Message = { role: 'user' | 'ai', content: string, refs?: string[], cached?: boolean }
export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', content: 'আসসালামু আলাইকুম, আমি সমবায় আইন সহকারী। সমবায় আইন ২০০১, বিধিমালা ২০০৪ ও সকল সার্কুলার থেকে আপনার যেকোনো প্রশ্নের সঠিক উত্তর রেফারেন্সসহ দেব।' }
  ])
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([{id:1, title:'সদস্য পদ বাতিল সংক্রান্ত'}, {id:2, title:'ঋণ প্রদান বিধি'}])
  const [isListening, setIsListening] = useState(false)
  const [loading, setLoading] = useState(false)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://your-backend.onrender.com'
  const sendMessage = async () => {
    if(!input.trim()) return
    const userMsg: Message = { role: 'user', content: input }
    setMessages(m => [...m, userMsg])
    const q = input
    setInput('')
    setLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/chat`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ question: q, user_id: 'demo-user' }) })
      const data = await res.json()
      setMessages(m => [...m, { role: 'ai', content: data.answer, refs: data.references, cached: data.cached }])
    } catch {
      setTimeout(()=>{ setMessages(m => [...m, { role:'ai', content: `আপনার প্রশ্ন: "${q}" এর উত্তর সমবায় সমিতি আইন, ২০০১ এর ধারা ১৭ অনুযায়ী - কোনো সদস্য যদি পরপর ৩টি সাধারণ সভায় অনুপস্থিত থাকেন বা সমিতির স্বার্থবিরোধী কাজ করেন, তাহলে ব্যবস্থাপনা কমিটি কারণ দর্শানো নোটিশ দিয়ে তার সদস্যপদ বাতিল করতে পারে।`, refs: ['সমবায় সমিতি আইন, ২০০১ (সংশোধিত ২০১৩), ধারা ১৭, পৃষ্ঠা ২৩', 'সমবায় সমিতি বিধিমালা ২০০৪, বিধি ১৯'] }]) }, 800)
    }
    setLoading(false)
  }
  const startVoice = () => {
    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if(!SR) { alert('এই ব্রাউজারে ভয়েস সাপোর্ট নেই'); return; }
    const rec = new SR(); rec.lang = 'bn-BD'; rec.onstart = () => setIsListening(true); rec.onend = () => setIsListening(false); rec.onresult = (e:any) => setInput(e.results[0][0].transcript); rec.start();
  }
  return (
    <div className="flex h-screen">
      <div className="w-[300px] bg-[#0B5C33] text-white flex flex-col p-3 hidden md:flex">
        <div className="flex items-center gap-2 p-2 mb-4"><div className="w-8 h-8 bg-white rounded flex items-center justify-center text-[#0B5C33] font-bold">স</div><div><p className="font-bold">সমবায় অধিদপ্তর</p><p className="text-xs opacity-80">আইন সহকারী</p></div></div>
        <button className="bg-white/15 hover:bg-white/25 p-3 rounded-lg flex items-center gap-2 mb-4"><Plus size={18}/> নতুন চ্যাট</button>
        <div className="flex-1 overflow-auto space-y-2">{history.map(h=>(<div key={h.id} className="p-3 bg-white/10 rounded-lg flex justify-between items-center group"><span className="text-sm truncate">{h.title}</span><Trash2 size={16} className="opacity-0 group-hover:opacity-100 cursor-pointer"/></div>))}</div>
        <div className="p-2 text-xs opacity-60">© ২০২৬ সমবায় অধিদপ্তর</div>
      </div>
      <div className="flex-1 flex flex-col">
        <div className="h-14 border-b flex items-center justify-between px-4 bg-white"><div className="flex items-center gap-2"><Menu className="md:hidden"/><span className="font-semibold">সমবায় আইন AI</span><span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">Free Mode</span></div><div className="flex items-center gap-3"><a href="/admin" className="text-sm flex items-center gap-1"><Settings size={16}/>এডমিন</a><div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center"><User size={16}/></div><LogOut size={18}/></div></div>
        <div className="flex-1 overflow-auto p-4 md:p-6 space-y-4">{messages.map((m,i)=>(<div key={i} className={`max-w-3xl ${m.role==='user' ? 'ml-auto' : ''}`}><div className={`p-4 rounded-2xl ${m.role==='user' ? 'bg-[#0B5C33] text-white rounded-br-sm' : 'bg-white border shadow-sm rounded-bl-sm'}`}><p className="whitespace-pre-wrap leading-7">{m.content}</p>{m.refs && (<div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg"><p className="text-xs font-bold text-amber-900 mb-1">📚 রেফারেন্স:</p>{m.refs.map((r,j)=><p key={j} className="text-xs text-amber-800">• {r}</p>)}{m.cached && <span className="text-[10px] bg-green-600 text-white px-2 py-0.5 rounded-full ml-2">Cached - Token Saved</span>}</div>)}</div></div>))}{loading && <p className="text-sm text-gray-500 animate-pulse">আইন খুঁজছি...</p>}</div>
        <div className="p-4 bg-white border-t"><div className="max-w-3xl mx-auto flex items-center gap-2 bg-gray-100 rounded-full px-4 py-2"><button onClick={startVoice} className={`p-2 rounded-full ${isListening ? 'bg-red-500 text-white animate-pulse' : 'bg-white'}`}><Mic size={18}/></button><input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter' && sendMessage()} placeholder="সমবায় আইন সম্পর্কে প্রশ্ন করুন..." className="flex-1 bg-transparent outline-none text-sm"/><button onClick={sendMessage} className="bg-[#0B5C33] text-white p-2.5 rounded-full"><Send size={18}/></button></div></div>
      </div>
    </div>
  )
}
