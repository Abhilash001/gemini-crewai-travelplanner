# ✈️ AI-Powered Travel Planner - Angular 19

This is an Angular 19 conversion of the Streamlit travel planner application. It provides a modern, responsive interface for searching flights, hotels, and generating AI-powered travel itineraries.

## Features

- **Flight Search**: Search for flights between airports using IATA codes
- **Hotel Search**: Find hotels in your destination or custom location
- **AI Recommendations**: Get personalized recommendations for flights and hotels
- **Itinerary Generation**: Complete travel itinerary with AI suggestions
- **Multiple Search Modes**: Flights only, Hotels only, or Complete search
- **Responsive Design**: Works on desktop and mobile devices
- **Dark Theme**: Modern dark UI matching the original design

## Prerequisites

- Node.js (v18 or higher)
- npm (v9 or higher)
- Angular CLI (v19)

## Installation

1. **Install Angular CLI globally:**
   ```bash
   npm install -g @angular/cli@19
   ```

2. **Install project dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   ng serve
   ```

4. **Open your browser and navigate to:**
   ```
   http://localhost:4200
   ```

## Backend Requirements

The application expects a backend API running on `http://localhost:8000` with the following endpoints:

- `POST /search_flights/` - Flight search
- `POST /search_hotels/` - Hotel search  
- `POST /complete_search/` - Combined search with itinerary
- `POST /generate_itinerary/` - Generate travel itinerary

### API Request Formats

**Flight Search:**
```json
{
  "origin": "ATL",
  "destination": "LAX", 
  "outbound_date": "2025-06-03",
  "return_date": "2025-06-10"
}
```

**Hotel Search:**
```json
{
  "location": "LAX",
  "check_in_date": "2025-06-03", 
  "check_out_date": "2025-06-10"
}
```

**Complete Search:**
```json
{
  "flight_request": {
    "origin": "ATL",
    "destination": "LAX",
    "outbound_date": "2025-06-03", 
    "return_date": "2025-06-10"
  },
  "hotel_request": {
    "location": "LAX",
    "check_in_date": "2025-06-03",
    "check_out_date": "2025-06-10"  
  }
}
```

## Project Structure

```
src/
├── app/travel-planner
│   ├── travel-planner.component.ts    # Main component
│   ├── travel-planner.component.html  # HTML
│   └── travel-planner.component.html  # CSS
├── assets/                            # Static assets
├── favicon.ico                        # Default icon
├── index.html                         # Start HTML template
├── main.ts                            # Application bootstrap
├── styles.css                         # Global styles
└── ...
```

## Key Angular 19 Features Used

- **Standalone Components**: No NgModule needed
- **Reactive Forms**: For form handling and validation
- **HttpClient**: For API communication
- **Modern Bootstrap**: Using `bootstrapApplication`
- **Built-in Control Flow**: Using `@if`, `@for` directives
- **Signal-based Architecture**: Prepared for future Angular features

## Development Commands

- `ng serve` - Start development server
- `ng build` - Build for production
- `ng test` - Run unit tests
- `ng lint` - Run linting
- `ng generate component [name]` - Generate component

## Customization

### API Base URL
Update the `API_BASE_URL` constant in `travel-planner.component.ts`:

```typescript
private readonly API_BASE_URL = 'https://your-api-domain.com';
```

### Styling
- Global styles: `src/styles.css`
- Component styles: Inline in `travel-planner.component.ts`
- Dark theme colors can be customized in the component styles

### Form Validation
Form validation rules can be modified in the component constructor:

```typescript
this.travelForm = this.fb.group({
  origin: ['ATL', [Validators.required, Validators.minLength(3)]],
  destination: ['LAX', [Validators.required, Validators.minLength(3)]],
  // ... other fields
});
```

## Production Build

```bash
ng build --configuration production
```

The built files will be in the `dist/` directory, ready for deployment to any web server.

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

© 2025 Travel AI Solutions - All rights reserved