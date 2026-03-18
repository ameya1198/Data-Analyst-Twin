/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,html}'],
  theme: {
    extend: {
      colors: {
        anvaya: {
          navy:     '#26215C',
          purple:   '#534AB7',
          'purple-mid': '#7F77DD',
          lavender: '#EEEDFE',
          amber:    '#EF9F27',
          'amber-dark': '#BA7517',
        },
      },
      letterSpacing: {
        'anvaya-wide':   '0.18em',
        'anvaya-wider':  '0.26em',
        'anvaya-widest': '0.30em',
      },
      fontFamily: {
        sans:  ['system-ui', 'sans-serif'],
        serif: ['Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
