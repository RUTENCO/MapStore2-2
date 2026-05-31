/*
 * Copyright 2024, GeoSolutions Sas.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, { forwardRef } from 'react';

const MenuNavLink = forwardRef(({
    children,
    className,
    disabled,
    onClick,
    ...props
}, ref) => {
    const Element = disabled ? 'span' : 'a';

    return (
        <Element
            {...props}
            ref={ref}
            aria-disabled={disabled || undefined}
            onClick={disabled ? (event) => event.preventDefault() : onClick}
            className={`nav-link${disabled ? ' disabled' : ''}${className ? ` ${className}` : ''}`}
        >
            {children}
        </Element>
    );
});

export default MenuNavLink;
