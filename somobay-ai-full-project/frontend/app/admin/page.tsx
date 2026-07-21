
'use client'
import { useState } from 'react'
export default function Admin(){
  const [freeHours, setFreeHours] = useState(10)
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">এডমিন প্যানেল - সমবায় AI</h1>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-4 rounded-xl border"><p className="text-sm text-gray-500">মোট ইউজার</p><p className="text-2xl font-bold">10,542</p></div>
        <div className="bg-white p-4 rounded-xl border"><p className="text-sm text-gray-500">মোট প্রশ্ন</p><p className="text-2xl font-bold">54,210</p></div>
        <div className="bg-white p-4 rounded-xl border"><p className="text-sm text-gray-500">টোকেন সেভ</p><p className="text-2xl font-bold">৳ 3,420</p></div>
      </div>
      <div className="bg-white p-4 rounded-xl border mb-6">
        <h3 className="font-semibold mb-2">ফ্রি টাইম কন্ট্রোল</h3>
        <input type="range" min="1" max="24" value={freeHours} onChange={e=>setFreeHours(Number(e.target.value))} className="w-full"/>
        <p>ফ্রি ব্যবহার: {freeHours} ঘণ্টা / দিন</p>
      </div>
      <div className="bg-white p-4 rounded-xl border">
        <h3 className="font-semibold mb-2">ডকুমেন্ট ম্যানেজমেন্ট</h3>
        <ul className="text-sm space-y-1">
          <li>✅ সমবায় আইন ২০০১.pdf - Indexed</li>
          <li>✅ বিধিমালা ২০০৪.pdf - Indexed</li>
          <li>✅ সার্কুলার ২০২৩.pdf - Indexed</li>
        </ul>
      </div>
    </div>
  )
}
