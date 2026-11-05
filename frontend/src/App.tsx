import { useEffect, useMemo, useState, type FormEvent, type CSSProperties } from "react";
import {AlertTriangle,ArrowUpRight,CheckCircle2,Clock3,FileCode2,GitPullRequest,Loader2,ShieldCheck,XCircle} from "lucide-react";
import { api, type ReleaseReport } from "./api";

const demo: ReleaseReport = {release_id:"demo-8f3c2a",repository:"Sansshrey/ReleaseGuard-AI",title:"Harden release authentication and dependency policy",risk:{total:62,security:72,code_quality:48,dependency:61,testing:55,api_compatibility:38},decision:"pending",findings:[
 {severity:"critical",category:"security",file:"src/auth.py",line:42,evidence:"Authorization path lacks an explicit role check.",recommendation:"Require an allowlisted role before privileged mutation."},
 {severity:"high",category:"dependency",file:"requirements.txt",line:8,evidence:"Dependency is not pinned to a reviewed version.",recommendation:"Pin and review the resolved dependency version."},
 {severity:"medium",category:"testing",file:"tests/test_auth.py",line:71,evidence:"Changed authorization path has no matching regression test.",recommendation:"Add a regression test covering unauthorized access."}
],deployment_checklist:["Confirm release owner and maintenance window.","Verify CI is green and required reviewers have signed off.","Confirm monitoring, alert thresholds and support coverage.","Use a staged rollout or canary where supported.","Verify health checks and critical user journeys."],rollback_plan:["Pause rollout and notify the release owner.","Revert to the last known-good artifact or deployment revision.","Verify service health, data integrity and critical journeys.","Record the incident, decision and follow-up actions."]};

type RiskTone = "critical" | "elevated" | "safe";
const tone=(s: number): RiskTone => s>=70 ? "critical" : s>=45 ? "elevated" : "safe";
function Ring({score}: {score: number}){return <div className={"risk-ring "+tone(score)} style={{"--score":score} as CSSProperties}><div><strong>{score}</strong><span>/100</span></div></div>}
function Severity({value}: {value: string}){return <span className={"severity "+value}>{value}</span>}

export default function App(){
 const[id,setId]=useState(""),[report,setReport]=useState(demo),[loading,setLoading]=useState(false),[apiState,setApiState]=useState("Demo data"),[note,setNote]=useState(""),[error,setError]=useState("");
 useEffect(()=>{api.health().then(()=>setApiState("API connected")).catch(()=>setApiState("Demo data"))},[]);
 const f = report.findings ?? [];
 const r: NonNullable<ReleaseReport["risk"]> = report.risk ?? {};
 const dimensions: Array<[string, number | undefined]> = [
  ["Security", r.security],
  ["Code quality", r.code_quality],
  ["Dependencies", r.dependency],
  ["Testing", r.testing],
  ["API compatibility", r.api_compatibility],
 ];
 const counts=useMemo(()=>({critical:f.filter(x=>x.severity==="critical").length,high:f.filter(x=>x.severity==="high").length,medium:f.filter(x=>x.severity==="medium").length,low:f.filter(x=>x.severity==="low").length}),[f]);
 async function load(e: FormEvent<HTMLFormElement>){e.preventDefault();if(!id.trim())return;setLoading(true);setError("");try{setReport(await api.getReport(id.trim()));setApiState("Live report")}catch(x){setError(x instanceof Error ? x.message : "Request failed.")}finally{setLoading(false)}}
 async function decide(ok: boolean){if(!id.trim()||note.trim().length<3){setError("Enter a decision note before approving or rejecting.");return}setLoading(true);setError("");try{const u=ok?await api.approve(id.trim(),note.trim()):await api.reject(id.trim(),note.trim());setReport(await api.getReport(u.release_id));setNote("")}catch(x){setError(x instanceof Error ? x.message : "Decision request failed.")}finally{setLoading(false)}}
 return <div className="shell">
  <aside className="side"><div className="brand"><div className="mark"><ShieldCheck size={21}/></div><div><b>ReleaseGuard</b><small>AI Release Governance</small></div></div>
   <nav><a className="active"><GitPullRequest size={17}/>Release overview</a><a><ShieldCheck size={17}/>Security</a><a><FileCode2 size={17}/>Code & dependencies</a><a><Clock3 size={17}/>Audit history</a></nav>
   <div className="sidefoot"><i/> {apiState}</div>
  </aside>
  <main><header><div><p className="eyebrow">RELEASE GOVERNANCE</p><h1>Release assessment</h1></div><form onSubmit={load} className="lookup"><input value={id} onChange={e=>setId(e.target.value)} placeholder="Paste release ID"/><button>{loading?<Loader2 className="spin" size={16}/>:"Load report"}</button></form></header>
   {error&&<div className="error"><AlertTriangle size={18}/>{error}</div>}
   <section className="hero"><div className="repo"><div className="repoicon"><GitPullRequest size={20}/></div><div><span>{report.repository}</span><h2>{report.title}</h2><small>Assessment ID · {report.release_id}</small></div></div><div className="herorisk"><Ring score={r.total||0}/><div><span>Overall risk</span><strong className={tone(r.total||0)}>{tone(r.total||0)}</strong><small>Deterministic weighted score</small></div></div></section>
   <section className="metrics">{Object.entries(counts).map(([k,v])=><div className="metric" key={k}><span>{k}</span><strong>{v}</strong></div>)}</section>
   <div className="grid"><section className="panel"><div className="panelhead"><div><p className="eyebrow">EVIDENCE</p><h3>Release findings</h3></div><span className="count">{f.length} findings</span></div>
    {f.map((x,i)=><article className="finding" key={x.file+i}><div><Severity value={x.severity}/><span className="cat">{x.category}</span></div><h4>{x.title||x.category}{x.file&&<span> · {x.file}{x.line?":"+x.line:""}</span>}</h4><p>{x.description||x.evidence}</p><div className="recommend"><ArrowUpRight size={15}/>{x.recommendation}</div></article>)}
   </section>
   <section className="panel"><div className="panelhead"><div><p className="eyebrow">RISK DIMENSIONS</p><h3>Why this score?</h3></div></div>
    {dimensions.map(([label, value]) => <div className="barrow" key={label}><div><span>{label}</span><b>{value ?? 0}</b></div><div className="bar"><i style={{width:(value ?? 0)+"%"}}/></div></div>)}
   </section></div>
   <div className="grid lower"><section className="panel"><div className="panelhead"><div><p className="eyebrow">DEPLOYMENT</p><h3>Release checklist</h3></div></div><ul className="checks">{(report.deployment_checklist||[]).map(x=><li key={x}><CheckCircle2 size={16}/>{x}</li>)}</ul></section>
   <section className="panel"><div className="panelhead"><div><p className="eyebrow">RECOVERY</p><h3>Rollback plan</h3></div></div><ol className="rollback">{(report.rollback_plan||[]).map(x=><li key={x}>{x}</li>)}</ol></section></div>
   <section className="approval"><div><p className="eyebrow">HUMAN DECISION</p><h3>{report.decision==="review_required"?"Review before release":"Release "+report.decision}</h3><p>{report.decision==="review_required"?"AI findings inform the decision. A human remains responsible for approval or rejection.":report.human_approval_note||"Decision recorded."}</p></div>
   {report.decision==="review_required"&&<div className="decision"><input value={note} onChange={e=>setNote(e.target.value)} placeholder="Decision note"/><button className="reject" disabled={loading} onClick={()=>decide(false)}><XCircle size={16}/>Reject</button><button className="approve" disabled={loading} onClick={()=>decide(true)}><CheckCircle2 size={16}/>Approve</button></div>}</section>
  </main>
 </div>
}