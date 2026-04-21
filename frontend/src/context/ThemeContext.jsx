'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext({
    theme: 'light',
    toggleTheme: () => {},
})

export const ThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('synapse-theme')
            if (saved) return saved
            return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
        }
        return 'light'
    })

    // Sync theme with DOM attribute
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme)
    }, [theme])

    const toggleTheme = () => {
        const newTheme = theme === 'light' ? 'dark' : 'light'
        setTheme(newTheme)
        localStorage.setItem('synapse-theme', newTheme)
        document.documentElement.setAttribute('data-theme', newTheme)
    }

    return (
        <ThemeContext.Provider value={{ theme, toggleTheme }}>
            <div className={`theme-root theme-${theme}`}>
                {children}
            </div>
        </ThemeContext.Provider>
    )
}

export const useTheme = () => useContext(ThemeContext)
