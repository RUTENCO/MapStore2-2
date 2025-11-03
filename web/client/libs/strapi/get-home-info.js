import { query } from './strapi.js';
const STRAPI_HOST = "http://localhost:1337"; // process.env.STRAPI_HOST;

export function getHomeInfo() {
    return query("home?populate=wrf_gif")
        .then(res => {
            const { wrf_gif } = res.data;
            const image = `${STRAPI_HOST}${wrf_gif.url}`;
            return { image };
        });
}
