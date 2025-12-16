import { useState, useRef, useEffect } from 'react';

export interface SelectOption {
  value: string;
  label: string;
  sublabel?: string;
  color?: string;
}

interface SearchableSelectProps {
  options: SelectOption[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  isLoading?: boolean;
  emptyMessage?: string;
}

export function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = 'Select an option...',
  searchPlaceholder = 'Search...',
  disabled = false,
  isLoading = false,
  emptyMessage = 'No options available',
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  const filteredOptions = options.filter(
    (opt) =>
      opt.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      opt.sublabel?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus input when dropdown opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSelect = (optionValue: string) => {
    onChange(optionValue);
    setIsOpen(false);
    setSearchQuery('');
  };

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
      if (!isOpen) {
        setSearchQuery('');
      }
    }
  };

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger button */}
      <button
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        className={`w-full flex items-center justify-between px-4 py-3 text-left bg-white border border-gray-300 rounded-lg shadow-sm transition-colors ${
          disabled
            ? 'bg-gray-50 cursor-not-allowed'
            : 'hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        } ${isOpen ? 'ring-2 ring-primary-500 border-primary-500' : ''}`}
      >
        {selectedOption ? (
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-md flex items-center justify-center text-white font-semibold text-sm flex-shrink-0"
              style={{ backgroundColor: selectedOption.color || '#3B82F6' }}
            >
              {selectedOption.label.charAt(0).toUpperCase()}
            </div>
            <div>
              <div className="font-medium text-gray-900">{selectedOption.label}</div>
              {selectedOption.sublabel && (
                <div className="text-sm text-gray-500">{selectedOption.sublabel}</div>
              )}
            </div>
          </div>
        ) : (
          <span className="text-gray-500">{placeholder}</span>
        )}
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
          {/* Search input */}
          <div className="p-2 border-b border-gray-100">
            <div className="relative">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <input
                ref={inputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          {/* Options list */}
          <div className="max-h-60 overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-3 text-center text-gray-500">
                <svg
                  className="animate-spin h-5 w-5 mx-auto text-primary-500"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              </div>
            ) : filteredOptions.length === 0 ? (
              <div className="px-4 py-3 text-center text-gray-500 text-sm">
                {searchQuery ? 'No matching organisations found' : emptyMessage}
              </div>
            ) : (
              filteredOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                    value === option.value ? 'bg-primary-50' : ''
                  }`}
                >
                  <div
                    className="w-8 h-8 rounded-md flex items-center justify-center text-white font-semibold text-sm flex-shrink-0"
                    style={{ backgroundColor: option.color || '#3B82F6' }}
                  >
                    {option.label.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 truncate">{option.label}</div>
                    {option.sublabel && (
                      <div className="text-sm text-gray-500 truncate">{option.sublabel}</div>
                    )}
                  </div>
                  {value === option.value && (
                    <svg
                      className="w-5 h-5 text-primary-500 flex-shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
