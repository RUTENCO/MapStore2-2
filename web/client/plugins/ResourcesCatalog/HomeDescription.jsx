/*
 * Copyright 2024, GeoSolutions Sas.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';
import { createPlugin } from "../../utils/PluginsUtils";
import HTML from '../../components/I18N/HTML';
import Text from '../../components/layout/Text';
import { Jumbotron } from 'react-bootstrap';
import PropTypes from 'prop-types';
import src from '../../product/assets/img/banner-Andina.png';
import miniciencias from '../../product/assets/img/logo-minciencias.png';
/**
 * This plugin shows a main description in the homepage
 * @memberof plugins
 * @class
 * @name HomeDescription
 * @prop {string} className custom class name (default `ms-home-description`)
 * @prop {string} backgroundSrc background image source (default `assets/img/hero.jpg`)
 * @prop {string} descriptionFooterMessageId custom description message id (default `home.shortDescription`)
 * @prop {object} style inline style
 */
function HomeDescription({
    className,
    backgroundSrc,
    style,
    descriptionFooterMessageId
}) {
    return (
        <Jumbotron
            className={`${className} ms-secondary-colors _padding-lg _relative`}
            style={{
                ...(backgroundSrc && {
                    backgroundImage: `url('${backgroundSrc}')`
                }),
                ...style
            }}
        >
            {descriptionFooterMessageId
                ? <Text textAlign="center" classNames={['_relative']}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <img
                            src={miniciencias}
                            alt="Miniciencias Logo"
                            style={{ height: '100px',
                                width: '200px',
                                paddingLeft: '10px',
                                objectFit: 'contain' }}
                        />
                        <HTML msgId={descriptionFooterMessageId}/>
                    </div>
                </Text>
                : null}
        </Jumbotron>
    );
}

HomeDescription.propTypes = {
    backgroundSrc: PropTypes.string,
    style: PropTypes.object,
    descriptionFooterMessageId: PropTypes.string,
    className: PropTypes.string
};

HomeDescription.defaultProps = {
    backgroundSrc: src,
    descriptionFooterMessageId: 'home.shortDescription',
    className: 'ms-home-description'
};

export default createPlugin('HomeDescription', {
    component: HomeDescription
});
