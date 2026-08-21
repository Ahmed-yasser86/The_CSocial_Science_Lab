"use client"

import * as React from "react"
import { useState } from "react"
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Badge } from "@/components/ui/badge"

export interface ComboboxOption {
  value: string
  label: string
}

export interface ComboboxProps {
  items: ComboboxOption[]
  value?: string | string[]
  onChange: (value: string | string[]) => void
  placeholder?: string
  emptyLabel?: string
  searchPlaceholder?: string
  multiple?: boolean
  disabled?: boolean
  className?: string
  contentClassName?: string
}

export function Combobox({
  items,
  value,
  onChange,
  placeholder = "Select an option…",
  emptyLabel = "No results found.",
  searchPlaceholder = "Search…",
  multiple = false,
  disabled = false,
  className,
  contentClassName,
}: ComboboxProps) {
  const [open, setOpen] = useState(false)

  const selectedValues = multiple
    ? (Array.isArray(value) ? value : value ? [value] : [])
    : value && !Array.isArray(value)
      ? [value]
      : []
  const selectedLabels = items
    .filter((item) => selectedValues.includes(item.value))
    .map((item) => item.label)

  function selectItem(item: ComboboxOption) {
    if (multiple) {
      const current = selectedValues.includes(item.value)
        ? selectedValues.filter((v) => v !== item.value)
        : [...selectedValues, item.value]
      onChange(current)
    } else {
      onChange(item.value)
      setOpen(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              "w-full justify-between font-normal",
              selectedValues.length === 0 && "text-muted-foreground",
              className
            )}
          />
        }
      >
        {selectedValues.length === 0 ? (
          placeholder
        ) : multiple ? (
          <span className="flex flex-wrap gap-1">
            {selectedLabels.map((label) => (
              <Badge key={label} variant="secondary">
                {label}
              </Badge>
            ))}
          </span>
        ) : (
          <span className="truncate">{selectedLabels[0]}</span>
        )}
        <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" aria-hidden />
      </PopoverTrigger>
      <PopoverContent className={cn("w-72 p-0", contentClassName)}>
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyLabel}</CommandEmpty>
            <CommandGroup>
              {items.map((item) => {
                const selected = selectedValues.includes(item.value)
                return (
                  <CommandItem
                    key={item.value}
                    value={`${item.value} ${item.label}`}
                    data-checked={selected || undefined}
                    onSelect={() => selectItem(item)}
                  >
                    {item.label}
                    {multiple ? (
                      <span className="ml-auto flex size-4 items-center justify-center rounded-[4px] border border-input data-checked:border-primary data-checked:bg-primary data-checked:text-primary-foreground [&>svg]:size-3.5">
                        <CheckIcon
                          className={cn(!selected && "opacity-0")}
                          aria-hidden
                        />
                      </span>
                    ) : null}
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
