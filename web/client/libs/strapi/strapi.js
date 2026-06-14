const STRAPI_HOST = process.env.STRAPI_HOST;
const STRAPI_TOKEN = process.env.STRAPI_TOKEN;

export function query(url) {
    return fetch(`${STRAPI_HOST}/api/${url}`, {
        headers: {
            Authorization: `Bearer ${STRAPI_TOKEN}`
        }
    }).then(response => response.json());
}
