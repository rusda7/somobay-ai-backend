'use client'
import { useState } from 'react'
import { Mic, Send, Trash2, Plus, LogOut, User, Settings, Menu } from 'lucide-react'
type Message = { role: 'user' | 'ai', content: string, cached?: boolean }
export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', content: 'আসসালামু আলাইকুম, আমি সমবায় আইন সহকারী।\n\nযেকোনো প্রশ্ন করুন, আমি সুনির্দিষ্ট উত্তর দেব।\nযেমন: "কমিটির মেয়াদ কত?" "৫০ ধারায় কি আছে?"' }
  ])
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([{id:1, title:'সদস্য পদ বাতিল'}, {id:2, title:'ঋণ প্রদান বিধি'}])
  const [isListening, setIsListening] = useState(false)
  const [loading, setLoading] = useState(false)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://somobay-ai-backend.onrender.com'
  
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
      setMessages(m => [...m, { role: 'ai', content: data.answer, cached: data.cached }])
    } catch {
      setMessages(m => [...m, { role:'ai', content: 'সার্ভার ব্যস্ত, ৫ সেকেন্ড পর আবার চেষ্টা করুন।' }])
    }
    setLoading(false)
  }

  const startVoice = () => {
    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if(!SR) { alert('ভয়েস সাপোর্ট নেই'); return; }
    const rec = new SR(); rec.lang = 'bn-BD'; rec.onstart = () => setIsListening(true); rec.onend = () => setIsListening(false); rec.onresult = (e:any) => setInput(e.results[0][0].transcript); rec.start();
  }

  return (
    <div className="flex h-screen bg-[#F5F7F6]">
      <div className="w-[300px] bg-[#0B5C33] text-white flex flex-col p-3 hidden md:flex">
        <div className="flex items-center gap-2 p-2 mb-4"><div className="w-8 h-8 bg-white rounded flex items-center justify-center text-[#0B5C33] font-bold">স</div><div><p className="font-bold">সমবায় অধিদপ্তর</p><p className="text-xs opacity-80">আইন সহকারী</p></div></div>
        <button onClick={()=>setMessages([messages[0]])} className="bg-white/15 hover:bg-white/25 p-3 rounded-lg flex items-center gap-2 mb-4"><Plus size={18}/> নতুন চ্যাট</button>
        <div className="flex-1 overflow-auto space-y-2">{history.map(h=>(<div key={h.id} className="p-3 bg-white/10 rounded-lg flex justify-between items-center group"><span className="text-sm truncate">{h.title}</span><Trash2 size={16} className="opacity-0 group-hover:opacity-100 cursor-pointer"/></div>))}</div>
        <div className="p-2 text-xs opacity-60">© ২০২৬ সমবায় অধিদপ্তর</div>
      </div>
      <div className="flex-1 flex flex-col">
        <div className="h-14 border-b flex items-center justify-between px-4 bg-white"><div className="flex items-center gap-2"><Menu className="md:hidden"/><span className="font-semibold">সমবায় আইন AI</span><span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">Specific Mode</span></div><div className="flex items-center gap-3"><a href="/admin" className="text-sm flex items-center gap-1"><Settings size={16}/>এডমিন</a><div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center"><User size={16}/></div><LogOut size={18}/></div></div>
        
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
          {messages.map((m,i)=>(
            <div key={i} className={`w-full max-w-3xl ${m.role==='user' ? 'ml-auto flex justify-end' : 'mr-auto'}`}>
              <div className={`px-5 py-4 rounded-2xl shadow-sm ${m.role==='user' ? 'bg-[#0B5C33] text-white rounded-br-sm max-w-[85%]' : 'bg-white border border-gray-100 rounded-bl-sm w-full'}`}>
                <p className="whitespace-pre-wrap break-words leading-7 text-[15px]">{m.content}</p>
                {/* No reference box - completely removed as requested */}
              </div>
            </div>
          ))}
          {loading && <p className="text-sm text-gray-500 animate-pulse ml-2">উত্তর তৈরি করছি...</p>}
        </div>

        <div className="p-4 bg-white border-t"><div className="max-w-3xl mx-auto flex items-center gap-2 bg-gray-100 rounded-full px-4 py-2"><button onClick={startVoice} className={`p-2.5 rounded-full ${isListening ? 'bg-red-500 text-white animate-pulse' : 'bg-white'}`}><Mic size={18}/></button><input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter' && sendMessage()} placeholder="প্রশ্ন লিখুন..." className="flex-1 bg-transparent outline-none text-sm"/><button onClick={sendMessage} className="bg-[#0B5C33] text-white p-2.5 rounded-full"><Send size={18}/></button></div></div>
      </div>
    </div>
  )
}
