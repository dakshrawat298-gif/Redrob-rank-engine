export default function Technologies() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg font-body text-text">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_16%,rgba(109,40,217,0.20),transparent_46%),radial-gradient(circle_at_90%_88%,rgba(59,130,246,0.18),transparent_46%)]" />

      <div className="relative h-full w-full px-[7vw] py-[8vh] flex flex-col">
        <div className="flex items-center gap-[1vw]">
          <span className="h-[0.35vh] w-[3.5vw] bg-gradient-to-r from-primary to-accent rounded-full" />
          <span className="font-mono text-[1.5vw] tracking-[0.3em] uppercase text-accent">09 / Stack</span>
        </div>
        <h2 className="mt-[2.4vh] text-[4.4vw] font-extrabold tracking-tight leading-[1.05] text-balance">
          The Arsenal
        </h2>

        <div className="mt-[5vh] grid grid-cols-2 gap-[2.2vw]">
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.3vw]">
            <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-accent mb-[1.8vh]">Core</div>
            <p className="text-[2vw] font-semibold text-text">Python · NumPy</p>
            <p className="mt-[1.2vh] text-[1.65vw] text-muted">Streaming data processing and vector math</p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.3vw]">
            <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-accent mb-[1.8vh]">Retrieval</div>
            <p className="text-[2vw] font-semibold text-text">FAISS · all-MiniLM-L6-v2</p>
            <p className="mt-[1.2vh] text-[1.65vw] text-muted">384-dim semantic recall at scale</p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.3vw]">
            <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-accent mb-[1.8vh]">Engine</div>
            <p className="text-[2vw] font-semibold text-text">ONNX Runtime · fastembed</p>
            <p className="mt-[1.2vh] text-[1.65vw] text-muted">CPU-only inference, zero GPU</p>
          </div>
          <div className="rounded-[0.9vw] border border-white/10 bg-white/[0.035] p-[2.3vw]">
            <div className="font-mono text-[1.5vw] tracking-[0.2em] uppercase text-accent mb-[1.8vh]">Delivery</div>
            <p className="text-[2vw] font-semibold text-text">Streamlit · GitHub</p>
            <p className="mt-[1.2vh] text-[1.65vw] text-muted">Interactive sandbox UI and version control</p>
          </div>
        </div>

        <div className="absolute bottom-[5vh] left-[7vw] right-[7vw] flex items-center justify-between font-mono text-[1.5vw] text-muted/80">
          <span>redrob-rank-engine</span>
          <span>09 / 10</span>
        </div>
      </div>
    </div>
  );
}
