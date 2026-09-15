import { Upload } from "lucide-react";
import { type ChangeEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import "./projects.css";

export function NewPitchProject(){
 const navigate=useNavigate();const [name,setName]=useState("");const [pitch,setPitch]=useState("");const [error,setError]=useState("");const [busy,setBusy]=useState(false);
 async function upload(event:ChangeEvent<HTMLInputElement>){const selected=event.target.files?.[0];if(!selected)return;if(!/\.(txt|md)$/i.test(selected.name)){setError("Upload a UTF-8 .txt or .md file.");return}const text=(await selected.text()).replace(/\r\n?/g,"\n");if(text.length>200000){setError("Pitch exceeds the 200,000 character limit.");return}setPitch(text);setError("")}
 async function submit(event:React.FormEvent){event.preventDefault();setBusy(true);setError("");try{const project=await api.createProject({display_name:name.trim(),company_aliases:[name.trim()],pitch_text:pitch});navigate(`/pitches/${project.project_id}/versions/${project.current_version_id}`)}catch(caught){setError(caught instanceof Error?caught.message:"Unable to save pitch");setBusy(false)}}
 return <section className="new-pitch-project"><header><h1>Create a pitch project</h1><p>Your original pitch is stored as an immutable version. Future edits create a new version without erasing prior assessments.</p></header><form onSubmit={submit}><label>Company name<input value={name} onChange={event=>setName(event.target.value)} required/></label><label>Pitch text<textarea rows={20} value={pitch} onChange={event=>setPitch(event.target.value.slice(0,200000))} required/></label><div className="project-upload"><label htmlFor="project-pitch-file"><Upload size={15}/> Upload pitch (.txt or .md)</label><input id="project-pitch-file" type="file" accept=".txt,.md,text/plain,text/markdown" onChange={upload}/><span>{pitch.length.toLocaleString()} / 200,000 characters</span></div>{error&&<p className="error" role="alert">{error}</p>}<button className="button" disabled={busy||!name.trim()||!pitch.trim()}>{busy?"Saving pitch…":"Create pitch project"}</button></form></section>
}
