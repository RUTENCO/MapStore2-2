/**
 * server/index.js
 * Proxy local para la API pública de estaciones agrícolas.
 * Expone solo /api/obtener_datos.php.
 */

const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });

const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.SENSORS_API_PORT || 3001;
const UPSTREAM_BASE_URL = process.env.STATS_API_BASE_URL || 'https://daa.yjk.mybluehost.me/api/obtener_datos.php';
const REQUEST_TIMEOUT_MS = Number(process.env.STATS_API_TIMEOUT_MS || 15000);

app.use(cors());
app.use(express.json());

function buildUrl(baseUrl, queryParams = {}) {
    const url = new URL(baseUrl);
    Object.entries(queryParams).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            url.searchParams.set(key, String(value));
        }
    });
    return url;
}

async function proxyToUpstream(req, res, queryParams = {}) {
    const url = buildUrl(UPSTREAM_BASE_URL, {
        ...req.query,
        ...queryParams
    });

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
        const upstreamResponse = await fetch(url, {
            method: 'GET',
            signal: controller.signal,
            headers: {
                accept: req.headers.accept || '*/*'
            }
        });

        const contentType = upstreamResponse.headers.get('content-type');
        if (contentType) {
            res.setHeader('content-type', contentType);
        }

        res.status(upstreamResponse.status);

        const body = await upstreamResponse.text();
        res.send(body);
    } catch (error) {
        const status = error?.name === 'AbortError' ? 504 : 502;
        res.status(status).json({
            error: 'No se pudo consultar la API pública',
            upstream: UPSTREAM_BASE_URL,
            details: error.message
        });
    } finally {
        clearTimeout(timeoutId);
    }
}

app.get('/api/obtener_datos.php', (req, res) => {
    proxyToUpstream(req, res);
});

app.use('/api', (req, res) => {
    res.status(404).json({
        error: 'Ruta no soportada por el proxy local',
        path: req.originalUrl,
        upstream: UPSTREAM_BASE_URL
    });
});

app.listen(PORT, () => {
    console.log(`Proxy de sensores corriendo en http://localhost:${PORT}`);
    console.log(`→ Upstream: ${UPSTREAM_BASE_URL}`);
});
