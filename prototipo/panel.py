from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

BASE = Path.home() / "vigilancia" / "prototipo"
DB = BASE / "datos" / "demo.db"
EVIDENCIAS = BASE / "datos" / "evidencias"

app = FastAPI(title="Prototipo de vigilancia")


def consultar(sql, parametros=()):
    if not DB.exists():
        return []

    with sqlite3.connect(DB) as conexion:
        conexion.row_factory = sqlite3.Row
        return [
            dict(fila)
            for fila in conexion.execute(sql, parametros)
        ]


@app.get("/api/resumen")
def resumen():
    tablas = ("sesiones", "objetos", "lecturas", "alertas", "listas")
    resultado = {}

    for tabla in tablas:
        filas = consultar(f"SELECT COUNT(*) AS n FROM {tabla}")
        resultado[tabla] = filas[0]["n"] if filas else 0

    return resultado


@app.get("/api/sesiones")
def sesiones():
    return consultar(
        "SELECT * FROM sesiones ORDER BY inicio DESC LIMIT 30"
    )


@app.get("/api/objetos")
def objetos():
    return consultar(
        "SELECT * FROM objetos ORDER BY id DESC LIMIT 100"
    )


@app.get("/api/lecturas")
def lecturas():
    return consultar(
        """SELECT lecturas.*, objetos.tipo, objetos.track_id
           FROM lecturas
           JOIN objetos ON objetos.id=lecturas.objeto_id
           ORDER BY lecturas.id DESC LIMIT 100"""
    )


@app.get("/api/alertas")
def alertas():
    return consultar(
        "SELECT * FROM alertas ORDER BY id DESC LIMIT 100"
    )


@app.get("/api/listas")
def listas():
    return consultar(
        "SELECT * FROM listas ORDER BY tipo, lista"
    )


@app.get("/evidencia/{nombre}")
def evidencia(nombre: str):
    ruta = EVIDENCIAS / nombre

    if ruta.name != nombre or not ruta.is_file():
        raise HTTPException(404, "Evidencia no encontrada")

    return FileResponse(ruta)


@app.get("/", response_class=HTMLResponse)
def inicio():
    return """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vigilancia Pi · Prototipo</title>
<style>
body{font-family:system-ui;background:#101827;color:#eef2f8;
margin:0;padding:24px}
main{max-width:1250px;margin:auto}
h1{margin-bottom:4px}
small{color:#a9b8ca}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0}
button{background:#263650;color:white;border:1px solid #40516d;
padding:10px 14px;border-radius:8px;cursor:pointer}
button:hover{background:#36517a}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
gap:12px;margin:20px 0}
.card{background:#1b293c;padding:18px;border-radius:12px}
.numero{font-size:30px;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:9px;text-align:left;border-bottom:1px solid #304057}
th{color:#9db3ce}
.contenedor{overflow-x:auto;background:#1b293c;border-radius:12px;
padding:14px}
a{color:#8ec8ff}
.aviso{background:#263650;border-radius:10px;padding:12px;margin:15px 0}
</style>
</head>
<body>
<main>
<h1>Vigilancia Pi</h1>
<small>Prototipo local · Raspberry Pi 5</small>
<div class="aviso">
DEMO: Las coincidencias y alertas son simuladas.
Las lecturas OCR requieren revisión humana.
</div>
<div id="resumen" class="cards"></div>
<nav>
<button onclick="cargar('sesiones')">Sesiones</button>
<button onclick="cargar('objetos')">Objetos</button>
<button onclick="cargar('lecturas')">OCR</button>
<button onclick="cargar('listas')">Listas</button>
<button onclick="cargar('alertas')">Alertas</button>
<button onclick="actualizar()">Actualizar</button>
</nav>
<h2 id="titulo">Objetos</h2>
<div class="contenedor" id="contenido">Cargando...</div>
</main>
<script>
let actual='objetos';

function seguro(valor){
  return String(valor??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;',
    '"':'&quot;',"'":'&#39;'
  })[c]);
}

async function resumen(){
  const r=await fetch('/api/resumen');
  const datos=await r.json();
  document.getElementById('resumen').innerHTML=
    Object.entries(datos).map(([k,v])=>
      `<div class="card"><div>${seguro(k)}</div>
       <div class="numero">${seguro(v)}</div></div>`
    ).join('');
}

async function cargar(tipo){
  actual=tipo;
  document.getElementById('titulo').textContent=
    tipo.toUpperCase();
  const r=await fetch('/api/'+tipo);
  const datos=await r.json();
  const cont=document.getElementById('contenido');

  if(!datos.length){
    cont.textContent='Todavía no hay registros.';
    return;
  }

  const columnas=Object.keys(datos[0]);
  cont.innerHTML='<table><thead><tr>'+
    columnas.map(c=>'<th>'+seguro(c)+'</th>').join('')+
    '</tr></thead><tbody>'+
    datos.map(fila=>'<tr>'+
      columnas.map(c=>{
        let valor=fila[c];
        if(c==='evidencia' && valor){
          return '<td><a target="_blank" href="/evidencia/'+
            encodeURIComponent(valor)+'">Ver imagen</a></td>';
        }
        return '<td>'+seguro(valor)+'</td>';
      }).join('')+'</tr>'
    ).join('')+'</tbody></table>';
}

async function actualizar(){
  await resumen();
  await cargar(actual);
}
actualizar();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
