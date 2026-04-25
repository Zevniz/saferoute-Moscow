import React from 'react';
import { Layers, Map as MapIcon, Satellite, Activity } from 'lucide-react';

export const LayerSwitcher = ({ setStyle, showTraffic, setShowTraffic }) => {
  return (
    <div className="absolute top-20 right-4 z-30 group">
      <div className="glass p-2 rounded-2xl flex flex-col gap-2 transition-all">
        <button onClick={() => setStyle('dark')} className="p-3 hover:bg-zinc-800 rounded-xl text-emerald-500">
          <MapIcon size={20} />
        </button>
        <button onClick={() => setStyle('satellite')} className="p-3 hover:bg-zinc-800 rounded-xl text-zinc-400">
          <Satellite size={20} />
        </button>
        <div className="h-[1px] bg-zinc-800 mx-2" />
        <button onClick={() => setShowTraffic(!showTraffic)} 
                className={`p-3 rounded-xl transition-all ${showTraffic ? 'bg-emerald-500 text-zinc-950' : 'text-zinc-400 hover:bg-zinc-800'}`}>
          <Activity size={20} />
        </button>
      </div>
    </div>
  );
};
