/*
 * Copyright 2025, Tu Organización.
 * All rights reserved.
 *
 * Este código fuente está licenciado bajo la licencia BSD que se encuentra en el archivo LICENSE en el directorio raíz de este proyecto.
 */

import React, { useState } from 'react';
import { createPlugin } from '../../utils/PluginsUtils';
import Message from '../../components/I18N/Message';
import { withResizeDetector } from 'react-resize-detector';
// import '../../themes/default/less/resources-catalog/_form-panel.less';

const WEB3FORMS_URL = 'https://api.web3forms.com/submit';
const WEB3FORMS_ACCESS_KEY = process.env.WEB3FORMS_ACCESS_KEY;

function HoverButton() {
    const [hover, setHover] = useState(false);
    return (
        <button
            type="submit"
            className={`ms-form-panel-btn${hover ? ' hover' : ''}`}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
        >
            <Message msgId="form.submit" defaultMessage="Enviar" />
        </button>
    );
}

function FormPanel() {
    const [message, setMessage] = useState(null);
    const [messageType, setMessageType] = useState(null);

    return (
        <div className="ms-form-panel">
            <h3><Message msgId="form.title" defaultMessage="PQRS / Contacto" /></h3>
            <form
                onSubmit={async(e) => {
                    e.preventDefault();
                    const formData = new FormData(e.target);
                    formData.append('access_key', WEB3FORMS_ACCESS_KEY);
                    let result;
                    try {
                        const response = await fetch(WEB3FORMS_URL, {
                            method: 'POST',
                            body: formData
                        });
                        result = await response.json();
                    } catch (error) {
                        setMessage('Hubo un error de red al enviar su PQRS. Por favor, inténtelo de nuevo.');
                        setMessageType('error');
                        return;
                    }
                    if (result && result.success) {
                        setMessage('Su PQRS ha sido enviada correctamente.');
                        setMessageType('success');
                        e.target.reset();
                    } else {
                        setMessage('Hubo un error al enviar su PQRS. Por favor, inténtelo de nuevo.');
                        setMessageType('error');
                    }
                }}
            >
                <label htmlFor="nombre"><Message msgId="form.name" defaultMessage="Nombre" /></label>
                <input type="text" id="nombre" name="nombre" required />

                <label htmlFor="telefono"><Message msgId="form.phone" defaultMessage="Teléfono" /></label>
                <input
                    type="tel"
                    id="telefono"
                    name="telefono"
                    required
                    pattern="[0-9]+"
                    inputMode="numeric"
                    onInput={e => {
                        e.target.value = e.target.value.replace(/[^0-9]/g, '');
                    }}
                />

                <label htmlFor="descripcion"><Message msgId="form.description" defaultMessage="Descripción" /></label>
                <textarea id="descripcion" name="descripcion" rows="4" required />

                <HoverButton />
            </form>
            {message && (
                <div className={`ms-form-message ${messageType}`}>{message}</div>
            )}
        </div>
    );
}

export default createPlugin('FormPanel', {
    component: withResizeDetector(FormPanel)
});
