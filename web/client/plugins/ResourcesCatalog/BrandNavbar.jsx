/*
 * Copyright 2024, GeoSolutions Sas.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, { useState, useMemo, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Glyphicon } from 'react-bootstrap';

import { createPlugin } from "../../utils/PluginsUtils";
import FlexBox from '../../components/layout/FlexBox';
import Menu from './components/Menu';
import usePluginItems from '../../hooks/usePluginItems';
import Button from '../../components/layout/Button';
import tooltip from '../../components/misc/enhancers/tooltip';
import Spinner from '../../components/layout/Spinner';
import MenuNavLink from './components/MenuNavLink';
import src from '../../product/assets/img/icono_inicio.png';

// Importa tu LESS (ajusta ruta si hace falta)
// import '../../themes/default/less/resources-catalog/_brand-navbar.less';
import covColombia from '../../product/assets/img/cov_colombia.png';

const ButtonWithTooltip = tooltip(Button);

/* --------------------
   Item component para el menu (botón/ícono)
   -------------------- */
function BrandNavbarMenuItem({ className, loading, glyph, labelId, onClick }) {
    return (
        <li className="ms-brand-navbar-item">
            <ButtonWithTooltip
                square
                borderTransparent
                tooltipId={labelId}
                tooltipPosition="bottom"
                onClick={onClick}
                className={`ms-menu-link${className ? ' ' + className : ''}`}
            >
                {loading ? <Spinner /> : <Glyphicon glyph={glyph} />}
            </ButtonWithTooltip>
        </li>
    );
}

BrandNavbarMenuItem.propTypes = {
    className: PropTypes.string,
    loading: PropTypes.bool,
    glyph: PropTypes.string,
    labelId: PropTypes.string,
    onClick: PropTypes.func
};

BrandNavbarMenuItem.defaultProps = {
    onClick: () => {}
};

/* --------------------
   Componente principal
   -------------------- */
function BrandNavbar({ size, variant, leftMenuItems, rightMenuItems, items, logo }, context) {
    const { loadedPlugins } = context;
    const configuredItems = usePluginItems({ items, loadedPlugins });

    const pluginLeftMenuItems = configuredItems
        .filter(({ target }) => target === 'left-menu')
        .map(item => ({ ...item, type: 'plugin' }));

    const pluginRightMenuItems = configuredItems
        .filter(({ target }) => target === 'right-menu')
        .map(item => ({ ...item, type: 'plugin' }));

    // Estado para menú hamburguesa (mobile)
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    // isMobile reactivo (escucha resize) para SSR safe
    const isClient = typeof window !== 'undefined';
    const [isMobile, setIsMobile] = useState(isClient ? window.innerWidth <= 768 : false);

    useEffect(() => {
        // Aseguramos siempre devolver una función (para evitar eslint consistent-return)
        if (!isClient) {
            return () => {};
        }
        const handleResize = () => setIsMobile(window.innerWidth <= 768);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [isClient]);

    // Helper: añade position y ordena por position
    const addPositionAndSort = (arr) =>
        arr
            .map((item, idx) => ({ ...item, position: item.position || idx + 1 }))
            .sort((a, b) => (a.position || 0) - (b.position || 0));

    // Asegura apariencia uniforme: inyecta className y variant por defecto
    const ensureMenuAppearance = (item) => ({
        ...item,
        className: item.className ? `${item.className} ms-menu-link` : 'ms-menu-link',
        variant: item.variant || 'default'
    });

    // Separar dropdowns (menú principal) de otros tipos de items y aplicar ensureMenuAppearance
    const dropdownMenuItems = useMemo(() => addPositionAndSort([
        ...leftMenuItems.filter(item => item.type === 'dropdown').map((menuItem, idx) => ({ ...menuItem, position: idx + 1 })),
        ...pluginLeftMenuItems.filter(item => item.type === 'dropdown')
    ]).map(ensureMenuAppearance), [leftMenuItems, pluginLeftMenuItems]);

    const otherLeftMenuItems = useMemo(() => addPositionAndSort([
        ...leftMenuItems.filter(item => item.type !== 'dropdown').map((menuItem, idx) => ({ ...menuItem, position: idx + 1 })),
        ...pluginLeftMenuItems.filter(item => item.type !== 'dropdown')
    ]).map(ensureMenuAppearance), [leftMenuItems, pluginLeftMenuItems]);

    const rightItemsSorted = useMemo(() => addPositionAndSort([
        ...rightMenuItems.map((menuItem, idx) => ({ ...menuItem, position: idx + 1 })),
        ...pluginRightMenuItems
    ]).map(ensureMenuAppearance), [rightMenuItems, pluginRightMenuItems]);

    // Render
    return (
        <>
            {/* Header GOV Colombia */}
            <div className="ms-header-gov" role="banner">
                <a href="https://www.gov.co/" target="_blank" rel="noopener noreferrer" aria-label="gov.co">
                    <img src={covColombia} alt="Gov.co" className="ms-header-gov-img" />
                </a>
            </div>

            <FlexBox
                id="ms-brand-navbar"
                classNames={[
                    'ms-brand-navbar',
                    'ms-main-colors',
                    'shadow-md',
                    '_sticky',
                    '_corner-tl',
                    '_padding-lr-sm',
                    '_padding-tb-xs'
                ]}
                centerChildrenVertically
                gap="sm"
                style={{ position: 'relative' }}
            >
                {/* Logo a la izquierda */}
                {logo && (
                    <MenuNavLink className="ms-brand-navbar-logo" href={logo.href || '#/'}>
                        <img
                            src={logo.src}
                            alt="Logo"
                            style={{ width: 'auto', height: '4.2rem', objectFit: 'contain', ...logo.style }}
                        />
                    </MenuNavLink>
                )}

                {/* Menú hamburguesa (mobile) */}
                {isMobile && dropdownMenuItems.length > 0 && (
                    <button
                        className="ms-menu-link ms-menu-hamburger-btn"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                        aria-expanded={mobileMenuOpen}
                        aria-controls="ms-mobile-dropdown"
                        aria-label={mobileMenuOpen ? "Cerrar menú" : "Abrir menú"}
                        type="button"
                    >
                        <Glyphicon glyph="menu-hamburger" />
                    </button>
                )}

                {/* Items izq (no dropdowns) — ocultos en mobile si se usa hamburguesa */}
                {!isMobile && otherLeftMenuItems.length > 0 && (
                    <Menu
                        centerChildrenVertically
                        gap="xs"
                        size={size}
                        variant={variant}
                        menuItemComponent={BrandNavbarMenuItem}
                        items={otherLeftMenuItems}
                    />
                )}

                {/* Dropdowns en desktop */}
                {!isMobile && dropdownMenuItems.length > 0 && (
                    <Menu
                        centerChildrenVertically
                        gap="xs"
                        size={size}
                        variant={variant}
                        menuItemComponent={BrandNavbarMenuItem}
                        items={dropdownMenuItems}
                        dropdownClassName="ms-brand-dropdown"
                    />
                )}

                {/* Right side (alineado a la derecha) */}
                <div className="ms-brand-navbar-right" aria-hidden={false}>
                    <Menu
                        centerChildrenVertically
                        gap="xs"
                        variant={variant}
                        alignRight
                        size={size}
                        menuItemComponent={BrandNavbarMenuItem}
                        items={rightItemsSorted}
                    />
                </div>

                {/* Mobile overlay + dropdown panel */}
                {isMobile && mobileMenuOpen && dropdownMenuItems.length > 0 && (
                    <>
                        <div
                            className="ms-mobile-dropdown-overlay"
                            onClick={() => setMobileMenuOpen(false)}
                            role="button"
                            aria-label="Cerrar menú"
                        />
                        <div id="ms-mobile-dropdown" className="ms-mobile-dropdown-menu" role="dialog" aria-modal="true">
                            {dropdownMenuItems.map((item, idx) => (
                                <Menu
                                    key={item.labelId || idx}
                                    vertical
                                    gap="xs"
                                    size={size}
                                    variant={variant}
                                    menuItemComponent={BrandNavbarMenuItem}
                                    items={[item]}
                                />
                            ))}
                        </div>
                    </>
                )}
            </FlexBox>
        </>
    );
}

BrandNavbar.propTypes = {
    size: PropTypes.string,
    variant: PropTypes.string,
    leftMenuItems: PropTypes.array,
    rightMenuItems: PropTypes.array,
    items: PropTypes.array,
    logo: PropTypes.object
};

BrandNavbar.contextTypes = {
    loadedPlugins: PropTypes.object
};

BrandNavbar.defaultProps = {
    logo: {
        src,
        href: '#/'
    },
    leftMenuItems: [
        {
            type: 'dropdown',
            labelId: 'Inicio',
            glyph: 'globe',
            variant: 'default',
            items: [
                { type: 'link', labelId: 'Portafolio', href: 'https://sites.google.com/view/sav-cardenas/publications?authuser=1' },
                { type: 'link', labelId: 'Servicios', href: '/pagina1/sub2' }
            ]
        },
        {
            type: 'dropdown',
            labelId: 'Quienes Somos',
            glyph: 'paperclip',
            variant: 'default',
            items: [
                { type: 'link', labelId: 'Subpágina 3', href: '/pagina2/sub3' },
                { type: 'link', labelId: 'Subpágina 4', href: '/pagina2/sub4' }
            ]
        },
        {
            type: 'dropdown',
            labelId: 'Nuestro Blog',
            glyph: 'folder-open',
            variant: 'default',
            items: [
                { type: 'link', labelId: 'Subpágina 5', href: '/pagina3/sub5' },
                { type: 'link', labelId: 'Subpágina 6', href: '/pagina3/sub6' }
            ]
        },
        {
            type: 'dropdown',
            labelId: 'Líneas de Investigación',
            glyph: 'question-sign',
            variant: 'default',
            items: [
                { type: 'link', labelId: 'Subpágina 7', href: '/pagina4/sub7' },
                { type: 'link', labelId: 'Subpágina 8', href: '/pagina4/sub8' }
            ]
        }
    ],
    rightMenuItems: []
};

export default createPlugin('BrandNavbar', {
    component: BrandNavbar
});
