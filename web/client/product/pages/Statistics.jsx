/*
 * Página Statistics - Portafolio
 */

import React from 'react';
import PropTypes from 'prop-types';
import Page from '../../containers/Page';

/**
 * @name Statistics
 * @memberof pages
 * @class
 * @classdesc
 * Página de estadísticas
 */
class StatisticsPage extends React.Component {
    static propTypes = {
        match: PropTypes.object,
        plugins: PropTypes.object,
        loaderComponent: PropTypes.func
    };

    static defaultProps = {
        mode: 'desktop'
    };

    render() {
        return (
            <Page
                id="statistics"
                plugins={this.props.plugins}
                params={this.props.match ? this.props.match.params : {}}
                loaderComponent={this.props.loaderComponent}
            />
        );
    }
}

export default StatisticsPage;
