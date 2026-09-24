import { useMemo, useState } from "react";

type Props = { name:string; src?:string; alt?:string; attribution?:string; sourceUrl?:string; showAttribution?:boolean; className?:string };
export function InvestorPortrait({name,src,alt,attribution,sourceUrl,showAttribution=false,className=""}:Props){
 const[failedSrc,setFailedSrc]=useState<string>();const initials=useMemo(()=>name.replace("-like Investor","").split(/\s+/).slice(0,2).map(x=>x[0]).join("").toUpperCase(),[name]);
 return <figure className={`investor-portrait ${className}`}>{src&&failedSrc!==src?<img src={src} alt={alt||`${name} portrait`} onError={()=>setFailedSrc(src)}/>:<div className="portrait-fallback" aria-label={`${name} portrait unavailable`}>{initials}</div>}{showAttribution&&attribution&&sourceUrl&&<figcaption><a href={sourceUrl} target="_blank" rel="noreferrer">{attribution}</a></figcaption>}</figure>
}
