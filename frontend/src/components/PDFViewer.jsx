import React, { useState, useEffect } from "react";
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";

export default function PDFViewer({ file, page = 1 }) {
  const [currentPage, setCurrentPage] = useState(page);
  const [zoom, setZoom] = useState(1.0);

  useEffect(() => setCurrentPage(page), [page]);

  if (!file) {
    return (
      <div className="p-6 text-center text-slate-400 border border-white/5 bg-slate-900/40 rounded-xl">
        No PDF selected
      </div>
    );
  }

  const pdfURL = `${file}#page=${currentPage}&zoom=${zoom * 100}`;

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-white/5 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800/70 border-b border-white/5">
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom(z => Math.min(3, z + 0.25))} className="p-2 bg-white/5 hover:bg-white/10 rounded">
            <ZoomIn size={16} />
          </button>
          <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="p-2 bg-white/5 hover:bg-white/10 rounded">
            <ZoomOut size={16} />
          </button>
          <button onClick={() => setZoom(1.0)} className="p-2 bg-white/5 hover:bg-white/10 rounded">
            <RotateCcw size={16} />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={() => setCurrentPage(p => Math.max(p - 1, 1))} className="p-2 bg-white/5 hover:bg-white/10 rounded">
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm text-slate-300">Page {currentPage}</span>
          <button onClick={() => setCurrentPage(p => p + 1)} className="p-2 bg-white/5 hover:bg-white/10 rounded">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="flex-1 bg-black/40 overflow-hidden">
        <iframe key={pdfURL} src={pdfURL} className="w-full h-full" title="PDF Viewer" />
      </div>
    </div>
  );
}
