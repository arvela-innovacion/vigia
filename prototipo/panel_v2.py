from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reglas_demo import (
    conectar, preparar, evaluar, guardar_lista
)

preparar()
app = FastAPI(title="Vigilancia Pi - Demo V2")


class Evaluacion(BaseModel):
    tipo: str
    identificador: str = Field(min_length=1, max_length=64)
    confianza: float = Field(default=1.0, ge=0, le=1)
    verificado: bool = False
    origen: str = "manual_demo"


class EntradaLista(BaseModel):
    tipo: str
    identificador: str = Field(min_length=1, max_length=64)
    lista: str
    descripcion: str = Field(default="", max_length=200)


class EstadoAlerta(BaseModel):
    estado: str


def filas(sql, parametros=()):
    with conectar() as db:
        return [
            dict(x) for x in db.execute(sql, parametros)
        ]


@app.get("/api/resumen")
def resumen():
    with conectar() as db:
        return {
            "objetos": db.execute(
                "SELECT COUNT(*) FROM objetos"
            ).fetchone()[0],
            "evaluaciones": db.execute(
                "SELECT COUNT(*) FROM evaluaciones_demo"
            ).fetchone()[0],
            "alertas_pendientes": db.execute(
                """SELECT COUNT(*) FROM alertas
                   WHERE estado='pendiente'"""
            ).fetchone()[0],
            "listas": db.execute(
                "SELECT COUNT(*) FROM listas"
            ).fetchone()[0],
        }


@app.get("/api/listas")
def listas():
    return filas(
        "SELECT * FROM listas ORDER BY tipo, identificador"
    )


@app.post("/api/listas")
def agregar_lista(datos: EntradaLista):
    try:
        guardar_lista(
            datos.tipo, datos.identificador,
            datos.lista, datos.descripcion
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@app.get("/api/evaluaciones")
def evaluaciones():
    return filas(
        """SELECT * FROM evaluaciones_demo
           ORDER BY id DESC LIMIT 100"""
    )


@app.post("/api/evaluar")
def nueva_evaluacion(datos: Evaluacion):
    try:
        return evaluar(
            datos.tipo, datos.identificador,
            datos.confianza, datos.verificado,
            datos.origen
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/alertas")
def alertas():
    return filas(
        """SELECT * FROM alertas
           ORDER BY id DESC LIMIT 100"""
    )


@app.post("/api/alertas/{alerta_id}/estado")
def cambiar_estado(alerta_id: int, datos: EstadoAlerta):
    if datos.estado not in ("pendiente", "revisada", "descartada"):
        raise HTTPException(400, "Estado no permitido")

    with conectar() as db:
        cursor = db.execute(
            """UPDATE alertas SET estado=?
               WHERE id=? AND simulada=1""",
            (datos.estado, alerta_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "Alerta simulada no encontrada")

    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def pagina():
    return """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vigilancia Pi V2</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0c1422;color:#e8eef7;
font-family:system-ui,Arial,sans-serif}
main{max-width:1150px;margin:auto;padding:24px}
h1{margin-bottom:3px}
h2{font-size:19px;margin-top:0}
p,.muted{color:#a7b6cb}
header{margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,
minmax(260px,1fr));gap:16px}
.panel{background:#17243a;border:1px solid #2a3d59;
border-radius:13px;padding:18px;margin-bottom:16px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);
gap:10px;margin-bottom:16px}
.stat{background:#17243a;padding:16px;border-radius:10px}
.stat b{display:block;font-size:28px;margin-top:5px}
input,select,button{font:inherit;padding:10px;border-radius:8px}
input,select{width:100%;background:#0e192b;color:white;
border:1px solid #435674;margin:6px 0 12px}
button{background:#3273d9;color:white;border:0;cursor:pointer}
button:hover{background:#4789ed}
button:disabled{opacity:.5}
label{font-size:13px;color:#b9c9dd}
.check{display:flex;align-items:center;gap:9px;margin:9px 0}
.check input{width:auto;margin:0}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:9px;border-bottom:1px solid #2d3e56;
text-align:left}
th{color:#9bb3d2}
.scroll{overflow-x:auto}
.critico{color:#ff7e7e;font-weight:700}
.ok{color:#77e2a3;font-weight:700}
.revision{color:#ffd17b;font-weight:700}
pre{white-space:pre-wrap;word-break:break-word;
background:#0c1422;padding:14px;border-radius:9px}
.notice{padding:13px;border-radius:9px;
background:#283852;margin:15px 0}
.actions{display:flex;gap:7px;flex-wrap:wrap}
.actions button{padding:6px 9px;font-size:12px}
@media(max-width:650px){.stats{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<main>
<header>
<h1>Vigilancia Pi · V2</h1>
<p>Prototipo de listas, reglas y alertas</p>
<div class="notice">
MODO DEMOSTRACIÓN. No se identifican personas reales.
Todas las alertas de este panel son simuladas.
</div>
</header>

<div id="stats" class="stats"></div>

<div class="grid">
<section class="panel">
<h2>Probar una identificación</h2>
<label>Tipo</label>
<select id="tipo">
<option value="matricula">Matrícula</option>
<option value="persona_demo">Persona ficticia</option>
</select>
<label>Identificador</label>
<input id="identificador" value="1234BCF">
<label>Confianza (0 a 1)</label>
<input id="confianza" type="number" min="0" max="1"
step="0.01" value="0.99">
<label>Origen</label>
<select id="origen" onchange="ajustarOrigen()">
<option value="manual_demo">Prueba manual ficticia</option>
<option value="ocr_candidato">Lectura OCR candidata</option>
</select>
<label class="check">
<input type="checkbox" id="verificado" checked>
Identificador verificado en la simulación
</label>
<button onclick="probar()">Evaluar</button>
<pre id="resultado">Esperando prueba...</pre>
</section>

<section class="panel">
<h2>Administrar listas ficticias</h2>
<label>Tipo</label>
<select id="tipoLista">
<option value="matricula">Matrícula</option>
<option value="persona_demo">Persona ficticia</option>
</select>
<label>Identificador</label>
<input id="idLista" placeholder="Ej.: TEST123">
<label>Lista</label>
<select id="lista">
<option value="negra">Negra · CRÍTICO</option>
<option value="blanca">Blanca · OK</option>
</select>
<label>Descripción</label>
<input id="descripcion" placeholder="Registro de demostración">
<button onclick="guardarLista()">Guardar entrada</button>
</section>
</div>

<section class="panel">
<h2>Alertas simuladas</h2>
<div id="alertas" class="scroll"></div>
</section>

<section class="panel">
<h2>Historial de evaluaciones</h2>
<div id="evaluaciones" class="scroll"></div>
</section>

<section class="panel">
<h2>Listas de demostración</h2>
<div id="listas" class="scroll"></div>
</section>

<button onclick="actualizar()">Actualizar todo</button>
</main>

<script>
function el(id){return document.getElementById(id)}
function esc(v){
return String(v??'').replace(/[&<>"']/g,c=>({
'&':'&amp;','<':'&lt;','>':'&gt;',
'"':'&quot;',"'":'&#39;'
})[c])
}
async function api(ruta,opciones){
const r=await fetch(ruta,opciones)
const datos=await r.json()
if(!r.ok)throw Error(JSON.stringify(datos))
return datos
}
function post(datos){
return {method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify(datos)}
}
function tabla(datos,columnas){
if(!datos.length)return '<p>Sin registros</p>'
return '<table><thead><tr>'+
columnas.map(c=>'<th>'+esc(c)+'</th>').join('')+
'</tr></thead><tbody>'+
datos.map(f=>'<tr>'+columnas.map(c=>
'<td>'+esc(f[c])+'</td>').join('')+'</tr>').join('')+
'</tbody></table>'
}
function ajustarOrigen(){
const ocr=el('origen').value==='ocr_candidato'
el('verificado').disabled=ocr
if(ocr)el('verificado').checked=false
}
async function probar(){
try{
const d=await api('/api/evaluar',post({
tipo:el('tipo').value,
identificador:el('identificador').value,
confianza:Number(el('confianza').value),
verificado:el('verificado').checked,
origen:el('origen').value
}))
el('resultado').textContent=JSON.stringify(d,null,2)
await actualizar()
}catch(e){el('resultado').textContent='ERROR: '+e.message}
}
async function guardarLista(){
try{
await api('/api/listas',post({
tipo:el('tipoLista').value,
identificador:el('idLista').value,
lista:el('lista').value,
descripcion:el('descripcion').value
}))
await actualizar()
alert('Entrada de demostración guardada')
}catch(e){alert('ERROR: '+e.message)}
}
async function estado(id,valor){
try{
await api('/api/alertas/'+id+'/estado',
post({estado:valor}))
await actualizar()
}catch(e){alert(e.message)}
}
async function actualizar(){
try{
const [s,a,e,l]=await Promise.all([
api('/api/resumen'),
api('/api/alertas'),
api('/api/evaluaciones'),
api('/api/listas')
])
el('stats').innerHTML=Object.entries(s).map(([k,v])=>
'<div class="stat">'+esc(k)+'<b>'+esc(v)+'</b></div>'
).join('')
el('evaluaciones').innerHTML=tabla(e,[
'id','tipo','identificador','confianza','origen',
'resultado','alerta_id','creada'
])
el('listas').innerHTML=tabla(l,[
'tipo','identificador','lista','descripcion'
])
if(!a.length){
el('alertas').innerHTML='<p>Sin alertas</p>'
}else{
el('alertas').innerHTML=
'<table><thead><tr><th>ID</th><th>Motivo</th>'+
'<th>Estado</th><th>Acciones</th></tr></thead><tbody>'+
a.map(x=>'<tr><td>'+esc(x.id)+'</td><td>'+
esc(x.motivo)+'</td><td>'+esc(x.estado)+'</td><td>'+
'<div class="actions">'+
'<button onclick="estado('+Number(x.id)+
',\\'revisada\\')">Revisada</button>'+
'<button onclick="estado('+Number(x.id)+
',\\'descartada\\')">Descartar</button>'+
'</div></td></tr>').join('')+'</tbody></table>'
}
}catch(e){console.error(e);alert('Error al cargar datos: '+e.message)}
}
ajustarOrigen()
actualizar()
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
