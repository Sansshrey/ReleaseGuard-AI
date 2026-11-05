const API_BASE=import.meta.env.VITE_API_BASE_URL||"http://127.0.0.1:8000";
const API_KEY=import.meta.env.VITE_API_KEY||"";
async function request(path,options={}){
 const headers={...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})};
 if(API_KEY)headers["X-API-Key"]=API_KEY;
 const r=await fetch(API_BASE+path,{...options,headers});
 const p=await r.json().catch(()=>({}));
 if(!r.ok)throw new Error(p.detail||p.error||"Request failed ("+r.status+")");
 return p;
}
export const api={
 health:()=>request("/health"),
 getReport:id=>request("/api/releases/"+encodeURIComponent(id)+"/report"),
 approve:(id,note)=>request("/api/releases/"+encodeURIComponent(id)+"/approve",{method:"POST",body:JSON.stringify({note})}),
 reject:(id,note)=>request("/api/releases/"+encodeURIComponent(id)+"/reject",{method:"POST",body:JSON.stringify({note})})
};