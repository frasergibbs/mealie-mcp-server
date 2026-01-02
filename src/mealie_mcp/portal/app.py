"""Lightweight FastAPI portal for meal planning rules configuration."""

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mealie_mcp.portal.rules import get_all, get_macros, get_rules, set_macros, set_rules

app = FastAPI(title="Meal Planning Rules Portal")


class RulesUpdate(BaseModel):
    rules: str


class MacrosUpdate(BaseModel):
    macros: dict


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meal Planning Rules</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 1rem;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: #00d9ff;
        }
        h2 {
            font-size: 1.1rem;
            margin: 1.5rem 0 0.75rem;
            color: #00d9ff;
        }
        .tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        .tab {
            padding: 0.5rem 1rem;
            background: #16213e;
            border: none;
            color: #aaa;
            cursor: pointer;
            border-radius: 0.5rem 0.5rem 0 0;
            font-size: 0.9rem;
        }
        .tab.active {
            background: #0f3460;
            color: #00d9ff;
        }
        .panel { display: none; }
        .panel.active { display: block; }
        textarea {
            width: 100%;
            min-height: 400px;
            background: #0f3460;
            border: 1px solid #00d9ff33;
            color: #eee;
            padding: 1rem;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.875rem;
            line-height: 1.5;
            border-radius: 0.5rem;
            resize: vertical;
        }
        textarea:focus { outline: 2px solid #00d9ff; }
        .macro-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
        }
        .day-card {
            background: #0f3460;
            padding: 1rem;
            border-radius: 0.5rem;
            border: 1px solid #00d9ff33;
        }
        .day-card h3 {
            font-size: 1rem;
            margin-bottom: 0.75rem;
            text-transform: capitalize;
            color: #00d9ff;
        }
        .macro-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        .macro-row label {
            font-size: 0.85rem;
            color: #aaa;
        }
        .macro-row input {
            width: 80px;
            padding: 0.35rem 0.5rem;
            background: #16213e;
            border: 1px solid #00d9ff33;
            color: #eee;
            border-radius: 0.25rem;
            text-align: right;
        }
        .macro-row input:focus { outline: 1px solid #00d9ff; }
        .btn {
            padding: 0.75rem 1.5rem;
            background: #00d9ff;
            color: #1a1a2e;
            border: none;
            border-radius: 0.5rem;
            font-weight: 600;
            cursor: pointer;
            margin-top: 1rem;
            font-size: 1rem;
        }
        .btn:hover { background: #00b8d4; }
        .btn:disabled { background: #555; cursor: not-allowed; }
        .status {
            margin-top: 0.75rem;
            padding: 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.85rem;
        }
        .status.success { background: #00ff8833; color: #00ff88; }
        .status.error { background: #ff000033; color: #ff6b6b; }
        .copy-all {
            margin-left: auto;
            padding: 0.35rem 0.75rem;
            background: #16213e;
            border: 1px solid #00d9ff33;
            color: #aaa;
            font-size: 0.8rem;
            cursor: pointer;
            border-radius: 0.25rem;
        }
        .copy-all:hover { background: #0f3460; color: #00d9ff; }
        .day-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🍽️ Meal Planning Rules</h1>

        <div class="tabs">
            <button class="tab active" data-tab="rules">Rules</button>
            <button class="tab" data-tab="macros">Daily Macros</button>
        </div>

        <div id="rules-panel" class="panel active">
            <textarea id="rules-editor"></textarea>
            <button class="btn" id="save-rules">Save Rules</button>
            <div id="rules-status" class="status" style="display:none;"></div>
        </div>

        <div id="macros-panel" class="panel">
            <div class="macro-grid" id="macros-grid"></div>
            <button class="btn" id="save-macros">Save Macros</button>
            <div id="macros-status" class="status" style="display:none;"></div>
        </div>
    </div>

    <script>
        const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
        const MACRO_FIELDS = ['calories', 'protein', 'carbs', 'fat'];
        let currentMacros = {};

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + '-panel').classList.add('active');
            });
        });

        // Load data
        async function loadData() {
            const res = await fetch('/api/rules');
            const data = await res.json();
            document.getElementById('rules-editor').value = data.rules;
            currentMacros = data.macros;
            renderMacros();
        }

        function renderMacros() {
            const grid = document.getElementById('macros-grid');
            grid.innerHTML = DAYS.map(day => `
                <div class="day-card">
                    <div class="day-header">
                        <h3>${day}</h3>
                        <button class="copy-all" data-day="${day}">Copy to all</button>
                    </div>
                    ${MACRO_FIELDS.map(field => `
                        <div class="macro-row">
                            <label>${field.charAt(0).toUpperCase() + field.slice(1)}${field === 'calories' ? '' : ' (g)'}</label>
                            <input type="number" data-day="${day}" data-field="${field}"
                                   value="${currentMacros[day]?.[field] || 0}">
                        </div>
                    `).join('')}
                </div>
            `).join('');

            // Copy to all buttons
            grid.querySelectorAll('.copy-all').forEach(btn => {
                btn.addEventListener('click', () => {
                    const sourceDay = btn.dataset.day;
                    DAYS.forEach(day => {
                        MACRO_FIELDS.forEach(field => {
                            currentMacros[day] = currentMacros[day] || {};
                            currentMacros[day][field] = currentMacros[sourceDay][field];
                        });
                    });
                    renderMacros();
                });
            });

            // Input handlers
            grid.querySelectorAll('input').forEach(input => {
                input.addEventListener('change', () => {
                    const { day, field } = input.dataset;
                    currentMacros[day] = currentMacros[day] || {};
                    currentMacros[day][field] = parseInt(input.value) || 0;
                });
            });
        }

        // Save rules
        document.getElementById('save-rules').addEventListener('click', async () => {
            const btn = document.getElementById('save-rules');
            const status = document.getElementById('rules-status');
            btn.disabled = true;
            try {
                const res = await fetch('/api/rules', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rules: document.getElementById('rules-editor').value })
                });
                if (res.ok) {
                    status.textContent = 'Rules saved!';
                    status.className = 'status success';
                } else {
                    throw new Error('Save failed');
                }
            } catch (e) {
                status.textContent = 'Error saving rules';
                status.className = 'status error';
            }
            status.style.display = 'block';
            btn.disabled = false;
            setTimeout(() => status.style.display = 'none', 3000);
        });

        // Save macros
        document.getElementById('save-macros').addEventListener('click', async () => {
            const btn = document.getElementById('save-macros');
            const status = document.getElementById('macros-status');
            btn.disabled = true;
            try {
                const res = await fetch('/api/macros', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ macros: currentMacros })
                });
                if (res.ok) {
                    status.textContent = 'Macros saved!';
                    status.className = 'status success';
                } else {
                    throw new Error('Save failed');
                }
            } catch (e) {
                status.textContent = 'Error saving macros';
                status.className = 'status error';
            }
            status.style.display = 'block';
            btn.disabled = false;
            setTimeout(() => status.style.display = 'none', 3000);
        });

        loadData();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the rules configuration portal."""
    return HTML_TEMPLATE


@app.get("/api/rules")
async def api_get_rules():
    """Get all meal planning configuration."""
    return JSONResponse(get_all())


@app.put("/api/rules")
async def api_update_rules(update: RulesUpdate):
    """Update the meal planning rules."""
    set_rules(update.rules)
    return {"status": "ok"}


@app.put("/api/macros")
async def api_update_macros(update: MacrosUpdate):
    """Update the per-day macros."""
    set_macros(update.macros)
    return {"status": "ok"}


def run_portal():
    """Run the portal server."""
    import uvicorn

    host = os.getenv("PORTAL_HOST", "0.0.0.0")
    port = int(os.getenv("PORTAL_PORT", "8081"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_portal()
