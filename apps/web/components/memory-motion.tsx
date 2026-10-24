"use client";

import { useState } from "react";

export function MemoryMotion() {
  const [paused, setPaused] = useState(false);
  return <div className="memory-motion" data-paused={paused}>
    <div className="motion-stage" aria-hidden="true">
      <div className="motion-source"><span /><span /><span /><i className="motion-scan" /></div>
      <div className="motion-track"><i /><i /><i /></div>
      <div className="motion-mark"><i /><i /><i /><i /></div>
      <div className="motion-track motion-track-out"><i /><i /><i /></div>
      <div className="motion-result"><span /><span /><b>↗</b></div>
    </div>
    <div className="motion-caption"><span><span className="motion-dots" aria-hidden="true"><i /><i /><i /></span>Fragments become context <small>Concept animation</small></span><button onClick={() => setPaused(!paused)} aria-label={paused ? "Play concept animation" : "Pause concept animation"}>{paused ? "Play" : "Pause"}</button></div>
  </div>;
}
